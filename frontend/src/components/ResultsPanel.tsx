'use client';

import { CodeResponse } from '@/types/coding';
import { formatCurrency } from '@/lib/api';
import IcdCodeCard from './IcdCodeCard';
import MultiCodeList from './MultiCodeList';
import AuditCard from './AuditCard';
import CandidateChart from './CandidateChart';
import RiskMeter from './RiskMeter';
import FhirPanel from './FhirPanel';
import { RotateCcw, Database, Clock } from 'lucide-react';

interface Props {
    result: CodeResponse;
    onReanalyze: () => void;
}

export default function ResultsPanel({ result, onReanalyze }: Props) {
    const delta = result.financial_delta ?? 0;

    return (
        <div className="flex flex-col gap-6 animate-slide-up">

            {/* ── Top summary strip ── */}
            <div className="glass-card px-6 py-4 flex flex-wrap items-center gap-6">
                <div className="flex flex-col gap-0.5">
                    <span className="mono-label">Session</span>
                    <span className="text-xs font-mono text-slate-300">{result.session_id.slice(0, 16)}…</span>
                </div>
                <div className="w-px h-8 bg-white/10" />
                <div className="flex flex-col gap-0.5">
                    <span className="mono-label">Mapping Path</span>
                    <span className={`text-xs font-mono font-semibold uppercase tracking-wider
            ${result.mapping_path === 'direct' ? 'text-success' :
                            result.mapping_path === 'embedding' ? 'text-warning' : 'text-slate-400'}`}>
                        {result.mapping_path}
                    </span>
                </div>
                <div className="w-px h-8 bg-white/10 hidden sm:block" />
                <div className="flex flex-col gap-0.5 hidden sm:flex">
                    <span className="mono-label">SNOMED</span>
                    <span className="text-xs font-mono text-slate-300">{result.resolved_snomed_code ?? '—'}</span>
                </div>
                <div className="w-px h-8 bg-white/10 hidden sm:block" />
                <div className="flex flex-col gap-0.5 hidden sm:flex">
                    <span className="mono-label">Revenue Impact</span>
                    <span className={`text-sm font-bold ${delta > 0 ? 'text-success' : delta < 0 ? 'text-danger' : 'text-slate-400'}`}>
                        {delta !== 0 ? formatCurrency(delta) : '—'}
                    </span>
                </div>
                <div className="ml-auto">
                    <button
                        onClick={onReanalyze}
                        className="flex items-center gap-2 text-xs text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg border border-white/10 hover:border-white/20"
                    >
                        <RotateCcw className="w-3 h-3" />
                        Re-analyse
                    </button>
                </div>
            </div>

            {/* ── Row 1: Primary code card + Risk meter ── */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="md:col-span-2">
                    <IcdCodeCard result={result} />
                </div>
                <div>
                    <RiskMeter score={result.risk_score} label={result.risk_label} confidence={result.confidence_score} />
                </div>
            </div>

            {/* ── Row 2: Multi-code list + Candidate chart ── */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <MultiCodeList codes={result.icd_codes} />
                <CandidateChart candidates={result.candidates} />
            </div>

            {/* ── Row 3: Audit card (full width if present) ── */}
            {result.discrepancy && (
                <AuditCard discrepancy={result.discrepancy} financialDelta={delta} drgFlag={result.drg_flag} />
            )}

            {/* ── Row 4: FHIR panel ── */}
            {result.fhir_condition && (
                <FhirPanel fhir={result.fhir_condition} />
            )}

            {/* ── Row 5: Metadata ── */}
            <div className="glass-card px-6 py-4 flex flex-wrap gap-6 items-center">
                <Database className="w-4 h-4 text-slate-600" />
                <div className="flex flex-col gap-0.5">
                    <span className="mono-label">Model</span>
                    <span className="text-xs font-mono text-slate-300">{result.extraction_metadata?.model ?? '—'}</span>
                </div>
                <div className="flex flex-col gap-0.5">
                    <span className="mono-label">ICD Version</span>
                    <span className="text-xs font-mono text-slate-300">{result.extraction_metadata?.icd_version ?? '—'}</span>
                </div>
                <div className="flex flex-col gap-0.5">
                    <span className="mono-label">SNOMED Version</span>
                    <span className="text-xs font-mono text-slate-300">{result.extraction_metadata?.snomed_version ?? '—'}</span>
                </div>
                <div className="flex flex-col gap-0.5">
                    <span className="mono-label">LLM Attempt</span>
                    <span className="text-xs font-mono text-slate-300">#{result.extraction_metadata?.attempt ?? 1}</span>
                </div>
                {result.error_at && (
                    <div className="flex items-center gap-2 text-xs text-danger-light">
                        <Clock className="w-3 h-3" />
                        Error at node: <span className="font-mono">{result.error_at}</span>
                    </div>
                )}
            </div>

        </div>
    );
}
