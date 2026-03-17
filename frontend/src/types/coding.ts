// types/coding.ts — TypeScript interfaces matching backend CodeResponse (Phase 6A)

export interface IcdCode {
    code: string;
    description: string;
    role: 'primary' | 'secondary' | 'additional';
    final_score: number;
    is_mcc: boolean;
    is_cc: boolean;
    base_reimbursement: number;
    rationale: string;
}

export interface CptCode {
    code: string;
    description: string;
    type: string;
    base_price: number;
    multiplier: number;
    gross_charge: number;
    confidence: number;
    original_text: string;
}

export interface FinancialSummary {
    total_estimated_revenue: number;
    pricing_multiplier: number;
    line_items: CptCode[];
}

export interface IcdCandidate {
    code: string;
    description: string;
    is_billable: boolean;
    is_cc: boolean;
    is_mcc: boolean;
    base_reimbursement: number;
    icd_version: string;
    mapping_type: string;
    confidence: number;
    is_primary: boolean;
    source: string;
    final_score: number;
}

export interface Discrepancy {
    type: string;
    ai_code: string;
    human_code: string;
    ai_description: string;
    human_description: string;
    explanation: string;
    revenue_delta: number;
    drg_flag: string | null;
    ai_is_mcc: boolean;
    ai_is_cc: boolean;
}

export interface FhirCoding {
    system: string;
    version: string;
    code: string;
    display: string;
    extension?: { url: string; valueString: string }[];
}

export interface FhirCondition {
    resourceType: string;
    id: string;
    clinicalStatus: { coding: { system: string; code: string }[] };
    verificationStatus: { coding: { system: string; code: string }[] };
    code: {
        coding: FhirCoding[];
        text: string;
    };
    subject: { reference: string };
    meta: { source: string };
}

export interface ExtractionMetadata {
    model: string;
    llm_version: string;
    icd_version: string;
    snomed_version: string;
    attempt: number;
}

export type DrgFlag = 'MCC_MISSED' | 'CC_MISSED' | 'MCC_OVERCODED' | null;
export type RiskLabel = 'LOW' | 'MEDIUM' | 'HIGH' | 'UNKNOWN';
export type MappingPath = 'direct' | 'embedding' | 'no_mapping' | 'embedding_failed' | 'no_snomed' | 'unknown';

export interface CodeResponse {
    session_id: string;
    final_icd_code: string;
    confidence_score: number;
    mapping_path: MappingPath;
    resolved_snomed_code: string | null;
    candidates: IcdCandidate[];
    icd_codes: IcdCode[];
    cpt_codes: CptCode[];
    financial_summary: FinancialSummary | null;
    discrepancy_type: string | null;
    discrepancy: Discrepancy | null;
    financial_delta: number | null;
    drg_flag: DrgFlag;
    risk_score: number;
    risk_label: RiskLabel;
    extraction_metadata: ExtractionMetadata;
    fhir_condition: FhirCondition | null;
    error_at: string | null;
    // Phase 6A — PDF upload
    document_source: 'text_input' | 'pdf_upload' | null;
    ocr_used: boolean | null;
}

export interface PipelineRequest {
    raw_text: string;
    human_icd_code?: string | null;
    org_id?: string | null;
}
