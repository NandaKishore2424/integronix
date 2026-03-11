// lib/api.ts — Typed API client for Integronix backend

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

/** POST /api/v1/code/run — accepts raw clinical text (JSON) */
export async function runCodingPipeline(params: PipelineRequest): Promise<CodeResponse> {
    const res = await fetch(`${API_BASE}/api/v1/code/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            raw_text: params.raw_text.trim(),
            human_icd_code: params.human_icd_code?.trim() || null,
        }),
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }

    return res.json() as Promise<CodeResponse>;
}

/** POST /api/v1/code/run-pdf — accepts multipart/form-data (PDF file) */
export async function runPdfPipeline(
    file: File,
    humanCode?: string | null,
): Promise<CodeResponse> {
    const form = new FormData();
    form.append('file', file);
    if (humanCode?.trim()) form.append('human_icd_code', humanCode.trim().toUpperCase());

    // Do NOT set Content-Type — browser adds multipart boundary automatically
    const res = await fetch(`${API_BASE}/api/v1/code/run-pdf`, {
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
    const abs = Math.abs(delta);
    const sign = delta >= 0 ? '+' : '-';
    return `${sign}$${abs.toLocaleString('en-US', { minimumFractionDigits: 0 })}`;
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

    const res = await fetch(`${API_BASE}/api/v1/cases?${params.toString()}`);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    return res.json() as Promise<CaseListResponse>;
}

/** GET /api/v1/cases/stats — KPI aggregates for the summary cards */
export async function fetchCaseStats(): Promise<CaseStatsResponse> {
    const res = await fetch(`${API_BASE}/api/v1/cases/stats`);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    return res.json() as Promise<CaseStatsResponse>;
}

/** GET /api/v1/cases/{session_id} — full result for a historical case */
export async function fetchCaseDetail(sessionId: string): Promise<CodeResponse> {
    const res = await fetch(`${API_BASE}/api/v1/cases/${sessionId}`);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    return res.json() as Promise<CodeResponse>;
}

// ── Phase 6C: Analytics API functions ───────────────────────────────────────

/** GET /api/v1/analytics/overview — KPI cards + 30-day trend */
export async function fetchAnalyticsOverview(): Promise<AnalyticsOverview> {
    const res = await fetch(`${API_BASE}/api/v1/analytics/overview`);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    return res.json() as Promise<AnalyticsOverview>;
}

/** GET /api/v1/analytics/top-codes — top 10 ICD codes by frequency */
export async function fetchTopCodes(): Promise<AnalyticsTopCodes> {
    const res = await fetch(`${API_BASE}/api/v1/analytics/top-codes`);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    return res.json() as Promise<AnalyticsTopCodes>;
}

/** GET /api/v1/analytics/discrepancy-breakdown — count per discrepancy type */
export async function fetchDiscrepancyBreakdown(): Promise<DiscrepancyPoint[]> {
    const res = await fetch(`${API_BASE}/api/v1/analytics/discrepancy-breakdown`);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`);
    }
    return res.json() as Promise<DiscrepancyPoint[]>;
}
