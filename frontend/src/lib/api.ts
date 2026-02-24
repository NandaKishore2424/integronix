// lib/api.ts — Typed API client for Integronix backend

import { CodeResponse, PipelineRequest } from '@/types/coding';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export class ApiError extends Error {
    constructor(public status: number, message: string) {
        super(message);
        this.name = 'ApiError';
    }
}

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

export function formatCurrency(delta: number): string {
    const abs = Math.abs(delta);
    const sign = delta >= 0 ? '+' : '-';
    return `${sign}$${abs.toLocaleString('en-US', { minimumFractionDigits: 0 })}`;
}

export function formatConfidence(score: number): string {
    return `${Math.round(score * 100)}%`;
}
