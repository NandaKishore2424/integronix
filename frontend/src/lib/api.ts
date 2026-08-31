// lib/api.ts — Typed API client for Integronix backend

import { supabase } from '@/lib/supabase';
import { CodeResponse, PipelineRequest } from '@/types/coding';
import { CaseListResponse, CaseStatsResponse, CasesFilters } from '@/types/cases';
import type { CodeResponse as FullCase } from '@/types/coding';
import { AnalyticsOverview, AnalyticsTopCodes, DiscrepancyPoint } from '@/types/analytics';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export class ApiError extends Error {
    constructor(public status: number, message: string) {
        super(message);
        this.name = 'ApiError';
    }
}

/**
 * Attach the caller's Supabase access token.
 *
 * Every /api/v1 endpoint verifies this token and derives the caller's
 * organization from it — the backend no longer trusts an org_id sent by the
 * client. Without this header the request is rejected with 401.
 */
async function authHeaders(): Promise<Record<string, string>> {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * fetch() with authentication. Use for every backend call.
 *
 * A 401 means the session lapsed mid-flight; bounce to login rather than
 * surfacing a confusing error deep in a component.
 */
async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
    const res = await fetch(input, {
        ...init,
        headers: {
            ...(init.headers as Record<string, string> | undefined),
            ...(await authHeaders()),
        },
    });

    if (res.status === 401 && typeof window !== 'undefined') {
        window.location.href = '/auth/login';
    }
    return res;
}

/** POST /api/v1/code/run — accepts raw clinical text (JSON) */
export async function runCodingPipeline(params: PipelineRequest): Promise<CodeResponse> {
    const res = await apiFetch(`${API_BASE}/api/v1/code/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            raw_text: params.raw_text.trim(),
            human_icd_code: params.human_icd_code?.trim() || null,
            org_id: params.org_id || null,
        }),
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }

    return res.json() as Promise<CodeResponse>;
}

export async function runPdfPipeline(
    file: File,
    humanCode?: string | null,
    orgId?: string | null,
): Promise<CodeResponse> {
    const form = new FormData();
    form.append('file', file);
    if (humanCode?.trim()) form.append('human_icd_code', humanCode.trim().toUpperCase());
    if (orgId) form.append('org_id', orgId);

    // Do NOT set Content-Type — browser adds multipart boundary automatically
    const res = await apiFetch(`${API_BASE}/api/v1/code/run-pdf`, {
        method: 'POST',
        body: form,
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }

    return res.json() as Promise<CodeResponse>;
}

export function formatCurrency(delta: number): string {
    // UI expects INR everywhere (RCM demo). Keep it consistent across pages.
    const abs = Math.abs(delta);
    const sign = delta >= 0 ? '+' : '-';
    return `${sign}₹${abs.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

export function formatConfidence(score: number): string {
    return `${Math.round(score * 100)}%`;
}

// ── Phase 6B: Case History API functions ────────────────────────────────────

/** GET /api/v1/cases — paginated case list with optional filters */
export async function fetchCases(filters: CasesFilters = {}): Promise<CaseListResponse> {
    const params = new URLSearchParams();
    params.set('page', String(filters.page ?? 1));
    params.set('page_size', '20');
    if (filters.risk_label)       params.set('risk_label',      filters.risk_label);
    if (filters.document_source)  params.set('document_source', filters.document_source);
    if (filters.branch_id)        params.set('branch_id',       filters.branch_id);

    const res = await apiFetch(`${API_BASE}/api/v1/cases?${params.toString()}`);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    return res.json() as Promise<CaseListResponse>;
}

/** GET /api/v1/cases/stats — KPI aggregates for the summary cards */
export async function fetchCaseStats(): Promise<CaseStatsResponse> {
    const res = await apiFetch(`${API_BASE}/api/v1/cases/stats`);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    return res.json() as Promise<CaseStatsResponse>;
}

/** GET /api/v1/cases/{session_id} — full result for a historical case */
export async function fetchCaseDetail(sessionId: string): Promise<CodeResponse> {
    const res = await apiFetch(`${API_BASE}/api/v1/cases/${sessionId}`);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    return res.json() as Promise<CodeResponse>;
}

// ── Phase 6C: Analytics API functions ───────────────────────────────────────

/** GET /api/v1/analytics/overview — KPI cards + 30-day trend */
export async function fetchAnalyticsOverview(orgId?: string): Promise<AnalyticsOverview> {
    const url = orgId ? `${API_BASE}/api/v1/analytics/overview?org_id=${orgId}` : `${API_BASE}/api/v1/analytics/overview`;
    const res = await apiFetch(url);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    return res.json() as Promise<AnalyticsOverview>;
}

/** GET /api/v1/analytics/top-codes — top 10 ICD codes by frequency */
export async function fetchTopCodes(orgId?: string): Promise<AnalyticsTopCodes> {
    const url = orgId ? `${API_BASE}/api/v1/analytics/top-codes?org_id=${orgId}` : `${API_BASE}/api/v1/analytics/top-codes`;
    const res = await apiFetch(url);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    return res.json() as Promise<AnalyticsTopCodes>;
}

/** GET /api/v1/analytics/discrepancy-breakdown — count per discrepancy type */
export async function fetchDiscrepancyBreakdown(orgId?: string): Promise<DiscrepancyPoint[]> {
    const url = orgId ? `${API_BASE}/api/v1/analytics/discrepancy-breakdown?org_id=${orgId}` : `${API_BASE}/api/v1/analytics/discrepancy-breakdown`;
    const res = await apiFetch(url);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    return res.json() as Promise<DiscrepancyPoint[]>;
}

export { fetchAnalyticsOverview as getAnalyticsOverview, fetchTopCodes as getTopCodes };

// ── Phase 7: RCM Claims Integration ─────────────────────────────────────────

export interface Payer {
    id: string;
    name: string;
    payer_type: string;
    base_allowed_multiplier: number;
}

export interface Claim {
    id: string;
    session_id: string;
    patient_name: string;
    status: string;
    total_billed_amount: number;
    total_allowed_amount: number;
    total_paid_amount: number;
    patient_responsibility: number;
    created_at: string;
    payers?: { name: string };
    claim_audit_logs?: Array<{
        id: string;
        previous_status: string | null;
        new_status: string;
        action_notes: string | null;
        created_at: string;
    }>;
}

export async function fetchPayers(): Promise<Payer[]> {
    const res = await apiFetch(`${API_BASE}/api/v1/claims/payers`);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    const data = await res.json();
    return data.payers as Payer[];
}

/** GET /api/v1/claims/payers/by-org/{orgId} — resolves the payer record for the logged-in user's org */
export async function fetchPayerByOrg(orgId: string): Promise<Payer | null> {
    const res = await apiFetch(`${API_BASE}/api/v1/claims/payers/by-org/${orgId}`);
    if (res.status === 404) return null;
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    const data = await res.json();
    return data.payer as Payer;
}

export async function submitClaim(payload: any): Promise<{ claim_id: string }> {
    const res = await apiFetch(`${API_BASE}/api/v1/claims/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }

    return res.json();
}

export async function fetchClaims(orgId: string): Promise<Claim[]> {
    const res = await apiFetch(`${API_BASE}/api/v1/claims/organization/${orgId}`);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    const data = await res.json();
    return data.claims as Claim[];
}

export async function fetchPayerClaims(payerId: string): Promise<Claim[]> {
    const res = await apiFetch(`${API_BASE}/api/v1/claims/payer/${payerId}`);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    const data = await res.json();
    return data.claims as Claim[];
}

export async function fetchClaimDetail(claimId: string): Promise<Claim> {
    const res = await apiFetch(`${API_BASE}/api/v1/claims/detail/${claimId}`);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    const data = await res.json();
    return data.claim as Claim;
}

export async function adjudicateClaim(claimId: string, payload: { action: 'APPROVE' | 'DENY'; payer_responsibility_pct: number; denial_reason?: string }): Promise<any> {
    const res = await apiFetch(`${API_BASE}/api/v1/claims/adjudicate/${claimId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    return res.json();
}

export async function appealClaim(claimId: string, justification: string): Promise<any> {
    const res = await apiFetch(`${API_BASE}/api/v1/claims/appeal/${claimId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ justification }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    return res.json();
}

export function exportEdiUrl(claimId: string): string {
    return `${API_BASE}/api/v1/claims/export/edi/${claimId}`;
}

/** Returns the URL for downloading the EDI 835 remittance advice (PAID / DENIED claims only) */
export function exportEdi835Url(claimId: string): string {
    return `${API_BASE}/api/v1/claims/export/edi835/${claimId}`;
}


// ── TICKET-04: Payer Edit Codes ───────────────────────────────────────────────

export interface PayerEditPayload {
    edited_icd_codes: Array<{ code: string; description: string }>;
    edited_cpt_codes: Array<{ cpt_code: string; description: string }>;
    edit_reason: string;
}

/** POST /api/v1/claims/edit/{claimId} — saves payer code corrections before approval */
export async function payerEditClaim(claimId: string, payload: PayerEditPayload): Promise<{ status: string; message: string; edit_id: string | null }> {
    const res = await apiFetch(`${API_BASE}/api/v1/claims/edit/${claimId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    return res.json();
}


// ── TICKET-08: Payer Automation Settings ─────────────────────────────────────

export type CustomRuleType =
    | 'max_amount'
    | 'exclude_cpt_prefix'
    | 'require_min_age'
    | 'require_max_age';

export interface CustomRule {
    rule_type: CustomRuleType;
    label: string;
    threshold?: number;       // used by max_amount  (INR)
    code_prefix?: string;     // used by exclude_cpt_prefix
    min_age?: number;         // used by require_min_age
    max_age?: number;         // used by require_max_age
}

export interface PayerSettings {
    payer_id: string;
    auto_approve_enabled: boolean;
    auto_approve_confidence_min: number;
    auto_approve_max_risk: number;
    auto_approve_requires_patient_dob: boolean;
    auto_approve_requires_patient_sex: boolean;
    auto_approve_payer_responsibility_pct: number;
    accepted_icd_versions: string[];
    auto_approve_custom_rules: CustomRule[];
}

/** GET /api/v1/payers/{payerId}/settings */
export async function getPayerSettings(payerId: string): Promise<PayerSettings> {
    const res = await apiFetch(`${API_BASE}/api/v1/payers/${payerId}/settings`);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    return res.json() as Promise<PayerSettings>;
}

/** PUT /api/v1/payers/{payerId}/settings */
export async function updatePayerSettings(
    payerId: string,
    payload: Omit<PayerSettings, 'payer_id'>,
): Promise<PayerSettings> {
    const res = await apiFetch(`${API_BASE}/api/v1/payers/${payerId}/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    return res.json() as Promise<PayerSettings>;
}
