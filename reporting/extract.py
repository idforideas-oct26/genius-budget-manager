"""
Budget Manager — Módulo de reportería, versión 2 (propuesta, archivo aparte).

Extrae campañas y gastos de la API REST y genera report.xlsx con:
  - Campañas            : todos los campos de la API + % ejecución + estado derivado
                          + revisión de datos (incluye gastos sin detalle), con formato
                          listo para enviar y alertas solo para campañas activas.
  - Resumen por cliente : totales calculados desde las campañas (no desde el
                          resumen global de la API, que mezcla clientes).
  - Gastos              : detalle de gastos registrados (tabla limpia para Power BI).
  - Gastos por categoría: matriz campaña x categoría.

Uso (desde cualquier carpeta):
    python extract.py

Requisitos:
    pip install openpyxl
    Budget Manager corriendo en http://localhost:8080  (mvn spring-boot:run)

Notas de diseño:
  - Las columnas derivadas se escriben como VALORES (no fórmulas): openpyxl no
    guarda valores calculados, y Power Query / pandas leerían celdas vacías.
  - Los umbrales de alerta son una propuesta pendiente de validar con el cliente.
"""

import json
import sys
import unicodedata
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

BUDGET_MANAGER_URL = 'http://localhost:8080'
OUTPUT_FILE = Path(__file__).with_name('report.xlsx')

# --- Supuestos (validar con el cliente) -------------------------------------
UMBRAL_AMARILLO = 0.90   # % de ejecución desde el cual se marca amarillo
UMBRAL_ROJO = 1.00       # % de ejecución sobre el cual se marca rojo
CATEGORIAS = ['ads_spend', 'creative', 'tools', 'agency_fee']  # según README
ETIQUETAS_CATEGORIA = {  # nombre legible para el reporte (el código original se conserva en 'Gastos')
    'ads_spend': 'Inversión en medios',
    'creative': 'Creatividad',
    'tools': 'Herramientas',
    'agency_fee': 'Honorarios de agencia',
}
NOMBRES_CLIENTE = {      # clave sin acentos ni mayúsculas -> nombre de presentación
    'suenosimple': 'SueñoSimple',
    'techstore': 'TechStore',
    'modalatam': 'ModaLatam',
}

FUENTE = 'Arial'
FMT_MONEDA = '#,##0'
FMT_PCT = '0.0%'
FMT_FECHA = 'dd/mm/yyyy'


# --- Acceso a la API ---------------------------------------------------------
def api_get(url: str):
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return json.loads(response.read())
    except urllib.error.URLError as exc:
        sys.exit(
            f'No se pudo conectar con {url}\n'
            f'Motivo: {exc.reason}\n'
            '¿Está corriendo Budget Manager (mvn spring-boot:run) en el puerto 8080?'
        )


def get_campaigns() -> list:
    return api_get(f'{BUDGET_MANAGER_URL}/api/campaigns')


def get_expenses(campaign_id: int) -> list:
    return api_get(f'{BUDGET_MANAGER_URL}/api/campaigns/{campaign_id}/expenses')


# --- Transformaciones --------------------------------------------------------
def normalizar_cliente(nombre: str) -> str:
    """'SuenoSimple' y 'SueñoSimple' deben ser el mismo cliente."""
    if not nombre:
        return 'Sin cliente'
    base = unicodedata.normalize('NFKD', nombre)
    clave = ''.join(ch for ch in base if not unicodedata.combining(ch)).lower().strip()
    return NOMBRES_CLIENTE.get(clave, nombre.strip())


def a_fecha(texto) -> date | None:
    try:
        return datetime.strptime(str(texto)[:10], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def estado_derivado(status: str, inicio: date | None, fin: date | None, hoy: date) -> str:
    """El estado original de la API NO se modifica; se agrega este aparte."""
    if status == 'active':
        return 'Vencida sin cerrar' if fin and fin < hoy else 'Activa'
    return {'closed': 'Cerrada', 'paused': 'Pausada', 'draft': 'Borrador'}.get(status, status)


def revision_datos(c: dict, inicio, fin, hoy: date) -> str:
    avisos = []
    if c['status'] == 'active' and fin and fin < hoy:
        avisos.append('Estado activo con fecha de fin vencida')
    if c['status'] == 'draft' and inicio and inicio < hoy:
        avisos.append('Borrador con fecha de inicio vencida')
    if c.get('spent', 0) > c.get('budget', 0):
        avisos.append('Gasto superior al presupuesto')
    return '; '.join(avisos)


def preparar_campanas(campaigns: list, hoy: date) -> list[dict]:
    filas = []
    for c in campaigns:
        presupuesto = float(c.get('budget') or 0)
        gastado = float(c.get('spent') or 0)
        inicio, fin = a_fecha(c.get('startDate')), a_fecha(c.get('endDate'))
        filas.append({
            'ID': c.get('id'),
            'Nombre': c.get('name'),
            'Cliente': normalizar_cliente(c.get('client')),
            'Tipo': c.get('type'),
            'Estado (API)': c.get('status'),
            'Estado derivado': estado_derivado(c.get('status'), inicio, fin, hoy),
            'Moneda': c.get('currency'),
            'Inicio': inicio,
            'Fin': fin,
            'Presupuesto': presupuesto,
            'Gastado': gastado,
            'Disponible': presupuesto - gastado,
            '% Ejecución': (gastado / presupuesto) if presupuesto else None,
            'Revisión de datos': revision_datos(c, inicio, fin, hoy),
        })
    return filas


def preparar_resumen(filas: list[dict]) -> list[dict]:
    por_cliente = defaultdict(list)
    for f in filas:
        por_cliente[f['Cliente']].append(f)
    resumen = []
    for cliente, items in sorted(por_cliente.items()):
        activas = [f for f in items if f['Estado (API)'] == 'active']
        vigentes = [f for f in activas if f['Estado derivado'] == 'Activa']
        p_act = sum(f['Presupuesto'] for f in activas)
        g_act = sum(f['Gastado'] for f in activas)
        resumen.append({
            'Cliente': cliente,
            'Campañas': len(items),
            'Activas (API)': len(activas),
            'Activas vigentes (por fecha)': len(vigentes),
            'Presupuesto activas': p_act,
            'Gastado activas': g_act,
            'Disponible activas': p_act - g_act,
            '% Consumo activas': (g_act / p_act) if p_act else None,
            'Presupuesto total': sum(f['Presupuesto'] for f in items),
            'Gastado total': sum(f['Gastado'] for f in items),
        })
    return resumen


def preparar_gastos(campaigns: list, filas: list[dict]) -> tuple[list[dict], list[dict]]:
    info = {f['ID']: f for f in filas}
    detalle = []
    for c in campaigns:
        for e in get_expenses(c['id']):
            detalle.append({
                'ID gasto': e.get('id'),
                'ID campaña': c['id'],
                'Campaña': info[c['id']]['Nombre'],
                'Cliente': info[c['id']]['Cliente'],
                'Categoría': e.get('category'),
                'Descripción': e.get('description'),
                'Monto': float(e.get('amount') or 0),
                'Fecha': a_fecha(e.get('date')),
            })
    matriz = []
    for f in filas:
        propios = [g for g in detalle if g['ID campaña'] == f['ID']]
        fila = {'ID': f['ID'], 'Campaña': f['Nombre'], 'Cliente': f['Cliente']}
        for cat in CATEGORIAS:
            fila[ETIQUETAS_CATEGORIA[cat]] = sum(g['Monto'] for g in propios if g['Categoría'] == cat)
        otras = sum(g['Monto'] for g in propios if g['Categoría'] not in CATEGORIAS)
        fila['Otras'] = otras
        registrado = sum(g['Monto'] for g in propios)
        fila['Total registrado'] = registrado
        fila['Gastado (campaña)'] = f['Gastado']
        fila['Sin detallar'] = f['Gastado'] - registrado
        matriz.append(fila)
    return detalle, matriz


# --- Escritura del Excel -----------------------------------------------------
def escribir_tabla(wb: Workbook, nombre_hoja: str, nombre_tabla: str, filas: list[dict],
                   formatos: dict, titulo_extra: str | None = None):
    ws = wb.create_sheet(nombre_hoja)
    if not filas:
        ws.append(['Sin datos'])
        return ws
    columnas = list(filas[0].keys())
    ws.append(columnas)
    for fila in filas:
        ws.append([fila[c] for c in columnas])

    fuente = Font(name=FUENTE, size=10)
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=len(columnas)):
        for celda in row:
            celda.font = fuente
            formato = formatos.get(columnas[celda.column - 1])
            if formato:
                celda.number_format = formato

    ref = f'A1:{get_column_letter(len(columnas))}{ws.max_row}'
    tabla = Table(displayName=nombre_tabla, ref=ref)
    tabla.tableStyleInfo = TableStyleInfo(name='TableStyleMedium2', showRowStripes=True)
    ws.add_table(tabla)
    ws.freeze_panes = 'A2'

    for i, nombre in enumerate(columnas, start=1):
        datos = max((len(str(f[nombre])) for f in filas if f[nombre] is not None), default=0)
        ancho = max(len(str(nombre)) + 6, datos + 3, 10)  # +6: espacio para la flecha del filtro
        ws.column_dimensions[get_column_letter(i)].width = min(ancho, 48)
        if ancho > 48:  # texto largo: ajustar en varias líneas en vez de cortarlo
            for fila_celdas in ws.iter_rows(min_row=2, min_col=i, max_col=i):
                fila_celdas[0].alignment = Alignment(wrap_text=True, vertical='top')
    return ws


def agregar_alertas(ws, columna_pct: str, hay_filas: bool):
    if not hay_filas:
        return
    rango = f'{columna_pct}2:{columna_pct}{ws.max_row}'
    ws.conditional_formatting.add(rango, CellIsRule(
        operator='greaterThan', formula=[str(UMBRAL_ROJO)],
        fill=PatternFill(start_color='F4B6B6', end_color='F4B6B6', fill_type='solid')))
    ws.conditional_formatting.add(rango, CellIsRule(
        operator='between', formula=[str(UMBRAL_AMARILLO), str(UMBRAL_ROJO)],
        fill=PatternFill(start_color='FFE699', end_color='FFE699', fill_type='solid')))


def agregar_alertas_activas(ws, col_pct: str, col_estado: str):
    """Amarillo/rojo solo si la campaña está activa (en una cerrada, el % es resultado final)."""
    rango = f'{col_pct}2:{col_pct}{ws.max_row}'
    ws.conditional_formatting.add(rango, FormulaRule(
        formula=[f'AND(${col_estado}2="active",${col_pct}2>{UMBRAL_ROJO})'],
        fill=PatternFill(start_color='F4B6B6', end_color='F4B6B6', fill_type='solid')))
    ws.conditional_formatting.add(rango, FormulaRule(
        formula=[f'AND(${col_estado}2="active",${col_pct}2>={UMBRAL_AMARILLO},${col_pct}2<={UMBRAL_ROJO})'],
        fill=PatternFill(start_color='FFE699', end_color='FFE699', fill_type='solid')))


def anotar_gastos_sin_detalle(filas: list[dict], matriz: list[dict]) -> None:
    """Marca campañas cuyo 'Gastado' no coincide con la suma de gastos registrados."""
    diferencia = {m['ID']: m['Sin detallar'] for m in matriz}
    for f in filas:
        d = diferencia.get(f['ID'], 0)
        if d > 0:
            aviso = f'Gastado sin detalle de gastos registrado: {d:,.0f}'
        elif d < 0:
            aviso = f'Gastos registrados superan lo gastado en {-d:,.0f}'
        else:
            continue
        f['Revisión de datos'] = '; '.join(x for x in [f['Revisión de datos'], aviso] if x)


def exportar(filas, resumen, detalle, matriz, hoy: date):
    wb = Workbook()
    wb.remove(wb.active)

    fmt_camp = {'Presupuesto': FMT_MONEDA, 'Gastado': FMT_MONEDA, 'Disponible': FMT_MONEDA,
                '% Ejecución': FMT_PCT, 'Inicio': FMT_FECHA, 'Fin': FMT_FECHA}
    ws = escribir_tabla(wb, 'Campañas', 'tblCampanas', filas, fmt_camp)
    if filas:
        columnas = list(filas[0].keys())
        agregar_alertas_activas(ws, get_column_letter(columnas.index('% Ejecución') + 1),
                                get_column_letter(columnas.index('Estado (API)') + 1))

    fmt_res = {c: FMT_MONEDA for c in ['Presupuesto activas', 'Gastado activas',
                                       'Disponible activas', 'Presupuesto total', 'Gastado total']}
    fmt_res['% Consumo activas'] = FMT_PCT
    ws2 = escribir_tabla(wb, 'Resumen por cliente', 'tblResumenCliente', resumen, fmt_res)
    if resumen:
        agregar_alertas(ws2, get_column_letter(list(resumen[0].keys()).index('% Consumo activas') + 1), True)

    escribir_tabla(wb, 'Gastos', 'tblGastos', detalle, {'Monto': FMT_MONEDA, 'Fecha': FMT_FECHA})

    fmt_mat = {c: FMT_MONEDA for c in list(ETIQUETAS_CATEGORIA.values()) + [
        'Otras', 'Total registrado', 'Gastado (campaña)', 'Sin detallar']}
    escribir_tabla(wb, 'Gastos por categoría', 'tblGastosCategoria', matriz, fmt_mat)

    notas = wb.create_sheet('Notas')
    for linea in [
        ['Reporte generado', hoy.strftime('%d/%m/%Y')],
        ['Fuente', f'{BUDGET_MANAGER_URL}/api/campaigns y /api/campaigns/{{id}}/expenses'],
        ['Estado derivado', 'Se calcula por fechas; el estado original de la API se conserva en "Estado (API)".'],
        ['Alertas de ejecución', f'Solo campañas activas: amarillo desde {UMBRAL_AMARILLO:.0%}, rojo sobre {UMBRAL_ROJO:.0%} (propuesta, por validar).'],
        ['Categorías de gasto', '; '.join(f'{v} = {k}' for k, v in ETIQUETAS_CATEGORIA.items())],
        ['Resumen por cliente', 'Calculado desde las campañas; no usa el resumen global de la API, que mezcla clientes.'],
        ['Sin detallar', 'Gastado de la campaña menos la suma de gastos registrados en el detalle.'],
    ]:
        notas.append(linea)
    notas.column_dimensions['A'].width = 24
    notas.column_dimensions['B'].width = 100
    for row in notas.iter_rows():
        for celda in row:
            celda.font = Font(name=FUENTE, size=10, bold=(celda.column == 1))

    wb.save(OUTPUT_FILE)


if __name__ == '__main__':
    hoy = date.today()
    print(f'Extrayendo datos — {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    campaigns = get_campaigns()
    print(f'Campañas encontradas: {len(campaigns)}')
    filas = preparar_campanas(campaigns, hoy)
    resumen = preparar_resumen(filas)
    detalle, matriz = preparar_gastos(campaigns, filas)
    anotar_gastos_sin_detalle(filas, matriz)
    print(f'Gastos registrados: {len(detalle)}')
    exportar(filas, resumen, detalle, matriz, hoy)
    print(f'Reporte guardado en {OUTPUT_FILE}')
