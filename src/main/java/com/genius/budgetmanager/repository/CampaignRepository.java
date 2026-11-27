package com.genius.budgetmanager.repository;

import com.genius.budgetmanager.model.Campaign;
import com.genius.budgetmanager.model.Expense;
import org.springframework.stereotype.Repository;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

@Repository
public class CampaignRepository {

    private final List<Campaign> campaigns = new ArrayList<>();
    private final List<Expense> expenses = new ArrayList<>();
    private long nextExpenseId = 11;
    private long nextCampaignId = 7;

    public CampaignRepository() {
        loadData();
    }

    private void loadData() {
        campaigns.add(new Campaign(1L, "Black Friday 2025 - Display", "SuenoSimple", "display", "closed",
                150000.0, 148200.0, "ARS", "2025-11-01", "2025-11-30"));
        campaigns.add(new Campaign(2L, "Email Recupero de Carritos", "SuenoSimple", "email", "active",
                30000.0, 12400.0, "ARS", "2026-01-01", "2026-03-31"));
        campaigns.add(new Campaign(3L, "Social Ads Q1 2026", "SuenoSimple", "social_ads", "active",
                120000.0, 67800.0, "ARS", "2026-01-01", "2026-03-31"));
        campaigns.add(new Campaign(4L, "Influencers Verano 2026", "SuenoSimple", "influencer", "paused",
                80000.0, 45000.0, "ARS", "2025-12-01", "2026-02-28"));
        campaigns.add(new Campaign(5L, "Google Ads Performance - Marzo", "TechStore", "search_ads", "active",
                200000.0, 195600.0, "ARS", "2026-03-01", "2026-03-31"));
        campaigns.add(new Campaign(6L, "Branding Digital Q2 2026", "TechStore", "branding", "draft",
                50000.0, 0.0, "ARS", "2026-04-01", "2026-06-30"));

        expenses.add(new Expense(1L, 1L, "Meta Ads - Black Friday", 85000.0, "ads_spend", "2025-11-05"));
        expenses.add(new Expense(2L, 1L, "Diseno de piezas graficas", 38200.0, "creative", "2025-11-03"));
        expenses.add(new Expense(3L, 1L, "Herramientas de analitica", 25000.0, "tools", "2025-11-01"));
        expenses.add(new Expense(4L, 2L, "Plataforma de email marketing", 8400.0, "tools", "2026-01-15"));
        expenses.add(new Expense(5L, 2L, "Copywriting campanas email", 4000.0, "creative", "2026-01-20"));
        expenses.add(new Expense(6L, 3L, "Meta Ads Enero", 22500.0, "ads_spend", "2026-01-10"));
        expenses.add(new Expense(7L, 3L, "Meta Ads Febrero", 24300.0, "ads_spend", "2026-02-10"));
        expenses.add(new Expense(8L, 3L, "TikTok Ads Febrero", 21000.0, "ads_spend", "2026-02-15"));
        expenses.add(new Expense(9L, 4L, "Honorarios influencers", 40000.0, "agency_fee", "2025-12-10"));
        expenses.add(new Expense(10L, 4L, "Produccion de contenido", 5000.0, "creative", "2025-12-15"));
    }

    public List<Campaign> findAll() {
        return new ArrayList<>(campaigns);
    }

    public Optional<Campaign> findById(Long id) {
        return campaigns.stream().filter(c -> c.getId().equals(id)).findFirst();
    }

    public Campaign saveCampaign(Campaign campaign) 
    {
    campaign.setId(nextCampaignId++);
    campaigns.add(campaign);
    return campaign;
    }


    public List<Expense> findExpensesByCampaignId(Long campaignId) {
        return expenses.stream()
                .filter(e -> e.getCampaignId().equals(campaignId))
                .collect(Collectors.toList());
    }

    public Expense saveExpense(Expense expense) {
        expense.setId(nextExpenseId++);
        expenses.add(expense);
        return expense;
    }
}
