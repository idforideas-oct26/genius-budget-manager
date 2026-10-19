"""
Budget Manager — Módulo de reportería
Extrae datos de la API REST y genera un archivo Excel con métricas de campañas.

Uso:
    python extract.py

Requisitos:
    pip install -r requirements.txt

El servidor de Budget Manager debe estar corriendo en http://localhost:8080
"""

import json
import urllib.request
import urllib.error
from datetime import datetime

BUDGET_MANAGER_URL = 'http://localhost:8080'
LANDING_CRM_URL    = 'http://localhost:3000'
OUTPUT_FILE        = 'report.xlsx'


def api_get(url: str) -> list | dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read())


def get_campaigns() -> list:
    """Obtiene todas las campañas del Budget Manager."""
    return api_get(f'{BUDGET_MANAGER_URL}/api/campaigns')


def get_budget_summary() -> dict:
    """Obtiene el resumen global de presupuesto (solo campañas activas)."""
    return api_get(f'{BUDGET_MANAGER_URL}/api/campaigns/summary')


def get_leads_summary() -> list:
    """Obtiene el resumen de leads por landing desde el Landing CRM."""
    return api_get(f'{LANDING_CRM_URL}/api/landings/summary')


def export_to_excel(campaigns: list, summary: dict) -> None:
    """Genera el archivo Excel con métricas de campañas y resumen formateados."""
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    wb = openpyxl.Workbook()

    # Estilos compartidos por las dos hojas.
    color_encabezado = PatternFill(fill_type='solid', fgColor='17365D')
    color_fila_alterna = PatternFill(fill_type='solid', fgColor='EAF1F8')
    borde_inferior = Border(
        bottom=Side(style='thin', color='D6DEE8')
    )

    # Hoja de campañas.
    ws = wb.active
    ws.title = 'Campañas'
    ws.append([
        'ID',
        'Nombre',
        'Cliente',
        'Estado',
        'Presupuesto',
        'Gastado',
        'Disponible',
    ])

    for campania in campaigns:
        presupuesto = campania.get('budget') or 0
        gastado = campania.get('spent') or 0

        ws.append([
            campania.get('id'),
            campania.get('name'),
            campania.get('client'),
            campania.get('status'),
            presupuesto,
            gastado,
            presupuesto - gastado,
        ])

    # Formato de encabezado: primera fila de la hoja.
    for celda in ws[1]:
        celda.fill = color_encabezado
        celda.font = Font(bold=True, color='FFFFFF', size=11)
        celda.alignment = Alignment(vertical='center')

    # Formato de datos: filas debajo del encabezado.
    for numero_fila in range(2, ws.max_row + 1):
        campania = campaigns[numero_fila - 2]
        moneda = str(campania.get('currency') or 'ARS').upper()
        formato_moneda = f'"{moneda}" #,##0.00;[Red]-"{moneda}" #,##0.00'

        # Las columnas E, F y G contienen importes.
        for columna in (5, 6, 7):
            celda = ws.cell(row=numero_fila, column=columna)
            celda.number_format = formato_moneda
            celda.alignment = Alignment(horizontal='right')

        # Agrega una línea inferior y alterna el color de las filas.
        for celda in ws[numero_fila]:
            celda.border = borde_inferior
            if numero_fila % 2 == 0:
                celda.fill = color_fila_alterna

    # Anchos de columna para que el texto no quede cortado.
    anchos = {
        'A': 10,
        'B': 36,
        'C': 22,
        'D': 16,
        'E': 20,
        'F': 20,
        'G': 20,
    }
    for columna, ancho in anchos.items():
        ws.column_dimensions[columna].width = ancho

    # Mantiene el encabezado visible y activa filtros.
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    ws.sheet_view.showGridLines = False
    ws.row_dimensions[1].height = 26

    # Hoja de resumen.
    ws2 = wb.create_sheet('Resumen')
    ws2.append(['Métrica', 'Valor'])
    ws2.append(['Campañas activas', summary.get('activeCampaigns', 0)])
    ws2.append(['Presupuesto total', summary.get('totalBudget', 0)])
    ws2.append(['Total gastado', summary.get('totalSpent', 0)])
    ws2.append(['Total disponible', summary.get('totalAvailable', 0)])

    # La API entrega el porcentaje como 56.5 para representar 56.5%.
    # Excel espera 0.565 cuando se usa el formato de porcentaje.
    porcentaje = summary.get('consumptionPercentage', 0) or 0
    ws2.append(['% de consumo', porcentaje / 100])

    # Formato de encabezado de la hoja de resumen.
    for celda in ws2[1]:
        celda.fill = color_encabezado
        celda.font = Font(bold=True, color='FFFFFF', size=11)
        celda.alignment = Alignment(vertical='center')

    # Formato de los valores del resumen.
    ws2['B2'].number_format = '0'
    formato_moneda_resumen = '"ARS" #,##0.00;[Red]-"ARS" #,##0.00'

    for numero_fila in (3, 4, 5):
        ws2.cell(row=numero_fila, column=2).number_format = formato_moneda_resumen
        ws2.cell(row=numero_fila, column=2).alignment = Alignment(horizontal='right')

    ws2['B6'].number_format = '0.00%'
    ws2['B6'].alignment = Alignment(horizontal='right')

    # Líneas y color alternado en las filas del resumen.
    for numero_fila in range(2, ws2.max_row + 1):
        for celda in ws2[numero_fila]:
            celda.border = borde_inferior
            if numero_fila % 2 == 0:
                celda.fill = color_fila_alterna

    ws2.column_dimensions['A'].width = 28
    ws2.column_dimensions['B'].width = 24
    ws2.freeze_panes = 'A2'
    ws2.auto_filter.ref = ws2.dimensions
    ws2.sheet_view.showGridLines = False
    ws2.row_dimensions[1].height = 26

    # Guarda el archivo Excel.
    wb.save(OUTPUT_FILE)
    print(f'Reporte guardado en {OUTPUT_FILE}')


if __name__ == '__main__':
    print(f'Extrayendo datos — {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    campaigns = get_campaigns()
    summary   = get_budget_summary()
    print(f'Campañas encontradas: {len(campaigns)}')
    export_to_excel(campaigns, summary)
