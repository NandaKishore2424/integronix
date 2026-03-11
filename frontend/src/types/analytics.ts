// types/analytics.ts — TypeScript interfaces for Phase 6C: Analytics Dashboard

export interface TrendPoint {
    date: string;      // "YYYY-MM-DD"
    cases: number;
    revenue: number;
}

export interface AnalyticsOverview {
    total_cases: number;
    total_revenue_recovered: number;
    avg_confidence: number;    // percentage 0-100
    high_risk_rate: number;    // percentage 0-100
    risk_distribution: {
        LOW: number;
        MEDIUM: number;
        HIGH: number;
    };
    source_distribution: {
        text_input: number;
        pdf_upload: number;
    };
    trend: TrendPoint[];       // 30-day daily array
}

export interface TopCodeItem {
    code: string;
    count: number;
    avg_revenue: number;
    avg_risk: number;
    top_discrepancy: string;
}

export interface AnalyticsTopCodes {
    codes: TopCodeItem[];
}

export interface DiscrepancyPoint {
    type: string;
    label: string;
    count: number;
}
