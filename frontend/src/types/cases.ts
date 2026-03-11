// types/cases.ts — TypeScript interfaces for Phase 6B: Case History

export interface CaseSummary {
    result_id: string;
    session_id: string;
    ai_icd_code: string | null;
    human_icd_code: string | null;
    discrepancy_type: string | null;
    financial_delta: number | null;
    risk_score: number;
    risk_label: 'LOW' | 'MEDIUM' | 'HIGH' | 'UNKNOWN';
    confidence_score: number;
    drg_flag: string | null;
    document_source: 'text_input' | 'pdf_upload' | null;
    ocr_used: boolean | null;
    text_snippet: string | null;
    created_at: string;  // ISO datetime string
}

export interface CaseListResponse {
    cases: CaseSummary[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
}

export interface CaseStatsResponse {
    total_cases: number;
    total_revenue_recovered: number;
    high_risk_count: number;
    accuracy_rate: number;  // 0-100
}

export interface CasesFilters {
    risk_label?: 'LOW' | 'MEDIUM' | 'HIGH' | '';
    document_source?: 'text_input' | 'pdf_upload' | '';
    branch_id?: string;
    page?: number;
}
