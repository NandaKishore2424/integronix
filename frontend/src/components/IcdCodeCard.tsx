'use client';

import { CodeResponse, MappingPath } from '@/types/coding';
import DrgBadge from './DrgBadge';
import { CheckCircle2, ArrowRight, TrendingUp } from 'lucide-react';

interface Props { result: CodeResponse }

// FIX FE-BUG-002: All 6 MappingPath values explicitly covered
const RESOLUTION_COLORS: Record<MappingPath, string> = {
    direct: 'text-success bg-success/10 border-success/25',
    embedding: 'text-warning bg-warning/10 border-warning/25',
    no_mapping: 'text-slate-400 bg-white/5 border-white/10',
    no_snomed: 'text-orange-400 bg-orange-500/10 border-orange-500/25',
    embedding_failed: 'text-danger bg-danger/10 border-danger/25',
    unknown: 'text-slate-500 bg-white/[0.03] border-white/[0.06]',
    who_api_icd11: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/25',
    who_api_icd10: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/25',
    provider_fallback: 'text-warning bg-warning/10 border-warning/25',
    provider_augmented: 'text-amber-400 bg-amber-500/10 border-amber-500/25',
};

const RESOLUTION_LABELS: Record<MappingPath, string> = {
    direct: '⚡ High Confidence',
    embedding: '🔍 Semantic Match',
    no_mapping: '⚠ Insufficient Data',
    no_snomed: '⚠ Ontology Gap',
    embedding_failed: '✕ Pipeline Error',
    unknown: '— Unresolved',
    who_api_icd11: '🌐 WHO ICD-11',
    who_api_icd10: '🌐 WHO ICD-10',
    provider_fallback: '📇 Provider Index',
    provider_augmented: '📇 Provider + Engine',
};

export default function IcdCodeCard({ result }: Props) {
    const primary = result.icd_codes?.[0];
    const pct = Math.round(result.confidence_score * 100);
    const resClass = RESOLUTION_COLORS[result.mapping_path] ?? RESOLUTION_COLORS['no_mapping'];
    const resLabel = RESOLUTION_LABELS[result.mapping_path] ?? RESOLUTION_LABELS['no_mapping'];

    return (
        <div className="glass-card p-6 h-full flex flex-col gap-5">

            {/* Header */}
            <div className="flex items-start justify-between flex-wrap gap-3">
                <div>
                    <p className="mono-label mb-1">Recommended Code</p>
                    <div className="flex items-center gap-3 flex-wrap">
                        <span className="text-4xl font-extrabold tracking-tight text-white font-mono">
                            {result.final_icd_code}
                        </span>
                        {result.final_icd_code !== 'UNKNOWN' && (
                            <CheckCircle2 className="w-6 h-6 text-success" />
                        )}
                    </div>
                </div>

                {/* Resolution quality badge */}
                <span className={`text-xs font-semibold uppercase tracking-wide px-3 py-1.5 rounded-lg border font-mono ${resClass}`}>
                    {resLabel}
                </span>
            </div>

            {/* Description */}
            {primary && (
                <p className="text-base text-slate-200 font-medium leading-relaxed">
                    {primary.description}
                </p>
            )}

            {/* Severity / billing classification chips */}
            {primary && (
                <div className="flex flex-wrap gap-2">
                    {primary.is_mcc && (
                        <span className="text-xs px-2.5 py-1 rounded-full border bg-danger/10 border-danger/30 text-danger-light font-semibold">
                            Major Complication — High Severity
                        </span>
                    )}
                    {primary.is_cc && !primary.is_mcc && (
                        <span className="text-xs px-2.5 py-1 rounded-full border bg-warning/10 border-warning/30 text-warning-light font-semibold">
                            Complication / Comorbidity
                        </span>
                    )}
                    {!primary.is_cc && !primary.is_mcc && (
                        <span className="text-xs px-2.5 py-1 rounded-full border bg-white/5 border-white/10 text-slate-400 font-semibold">
                            Standard Inpatient
                        </span>
                    )}
                    {primary.base_reimbursement > 0 && (
                        <span className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-full border bg-success/10 border-success/25 text-success font-semibold">
                            <TrendingUp className="w-3 h-3" />
                            ${primary.base_reimbursement.toLocaleString()} estimated reimbursement
                        </span>
                    )}
                </div>
            )}

            {/* Confidence bar */}
            <div>
                <div className="flex justify-between text-xs mb-2">
                    <span className="text-slate-500 font-medium">Recommendation Confidence</span>
                    <span className="font-bold text-white">{pct}%</span>
                </div>
                <div className="conf-bar-track">
                    <div
                        className="conf-bar-fill"
                        style={{ width: `${pct}%` }}
                    />
                </div>
            </div>

            {/* Clinical pathway trace */}
            {result.resolved_snomed_code && (
                <div className="flex items-center gap-2 pt-1 border-t border-white/[0.06] text-xs text-slate-500">
                    <ArrowRight className="w-3 h-3 text-accent" />
                    <span>Clinical concept</span>
                    <span className="font-mono text-slate-400">{result.resolved_snomed_code}</span>
                    <ArrowRight className="w-3 h-3 text-accent" />
                    <span className="font-mono text-slate-200">{result.final_icd_code}</span>
                </div>
            )}

            {/* DRG flag */}
            {result.drg_flag && <DrgBadge flag={result.drg_flag} />}

        </div>
    );
}
