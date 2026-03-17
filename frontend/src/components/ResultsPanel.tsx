'use client';

import { useState, useEffect } from 'react';
import { CodeResponse, MappingPath } from '@/types/coding';
import { formatCurrency, fetchPayers, submitClaim, Payer } from '@/lib/api';
import IcdCodeCard from './IcdCodeCard';
import MultiCodeList from './MultiCodeList';
import AuditCard from './AuditCard';
import CandidateChart from './CandidateChart';
import RiskMeter from './RiskMeter';
import FhirPanel from './FhirPanel';
import CptCodeList from './CptCodeList';
import { RotateCcw, ShieldCheck, AlertCircle, FileText, ScanText, IndianRupee, Landmark, Send, CheckCircle2 } from 'lucide-react';

interface Props {
    result: CodeResponse;
    onReanalyze: () => void;
    orgId?: string; // Phase 7: Need orgId to submit claim
}

// FIX FE-BUG-002: All 6 MappingPath values covered. Using Record<MappingPath, ...>
// gives TypeScript exhaustiveness — compiler errors if a new path is added without a label.
const RESOLUTION_LABELS: Record<MappingPath, { label: string; color: string }> = {
    direct: { label: 'High Confidence', color: 'text-success' },
    embedding: { label: 'Semantic Match', color: 'text-warning' },
    no_mapping: { label: 'Low Confidence', color: 'text-slate-400' },
    no_snomed: { label: 'Ontology Gap', color: 'text-orange-400' },
    embedding_failed: { label: 'Pipeline Error', color: 'text-danger' },
    unknown: { label: 'Unresolved', color: 'text-slate-500' },
};

export default function ResultsPanel({ result, onReanalyze, orgId = '00000000-0000-0000-0000-000000000001' }: Props) {
    const delta = result.financial_delta ?? 0;
    const res = RESOLUTION_LABELS[result.mapping_path] ?? RESOLUTION_LABELS['no_mapping'];

    const [payers, setPayers] = useState<Payer[]>([]);
    const [selectedPayer, setSelectedPayer] = useState<string>('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [submitSuccess, setSubmitSuccess] = useState(false);

    useEffect(() => {
        fetchPayers().then(data => {
            setPayers(data);
            if (data.length > 0) setSelectedPayer(data[0].id);
        }).catch(err => console.error("Failed to load payers", err));
    }, []);

    const handleSubmitClaim = async () => {
        if (!selectedPayer) return;
        setIsSubmitting(true);
        try {
            await submitClaim({
                session_id: result.session_id,
                organization_id: orgId,
                payer_id: selectedPayer,
                patient_name: ((result.fhir_condition?.subject as any)?.display) ?? 'John Doe', // Simulated patient for the demo
                patient_dob: '1980-01-01', // Simulated
                total_billed_amount: result.financial_summary?.total_estimated_revenue ?? 0,
                claim_data: result as any
            });
            setSubmitSuccess(true);
        } catch (err) {
            console.error("Failed to submit claim", err);
            alert("Failed to submit claim. It may have already been submitted.");
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="flex flex-col gap-6 animate-slide-up">

            {/* ── Top summary strip ── */}
            <div className="glass-card px-6 py-4 flex flex-wrap items-center gap-6">
                <div className="flex flex-col gap-0.5">
                    <span className="mono-label">Case ID</span>
                    <span className="text-xs font-mono text-slate-300">{result.session_id.slice(0, 16)}…</span>
                </div>
                <div className="w-px h-8 bg-white/10" />
                <div className="flex flex-col gap-0.5">
                    <span className="mono-label">Confidence</span>
                    <span className={`text-xs font-mono font-semibold uppercase tracking-wider ${res.color}`}>
                        {res.label}
                    </span>
                </div>
                <div className="w-px h-8 bg-white/10 hidden sm:block" />
                <div className="flex flex-col gap-0.5 sm:flex">
                    <span className="mono-label">Standard</span>
                    <span className="text-xs font-mono text-slate-300">ICD-10-CM 2024</span>
                </div>
                <div className="flex flex-col gap-0.5 sm:flex">
                    <span className="mono-label text-success-light">Hospital Revenue</span>
                    <span className="text-sm font-bold text-success flex items-center gap-1">
                        <IndianRupee className="w-3.5 h-3.5" />
                        {result.financial_summary?.total_estimated_revenue ? formatCurrency(result.financial_summary.total_estimated_revenue).replace('₹', '') : '—'}
                    </span>
                </div>
                <div className="w-px h-8 bg-white/10 hidden lg:block" />
                <div className="flex flex-col gap-0.5 sm:flex">
                    <span className="mono-label italic">Multiplier</span>
                    <span className="text-xs font-mono text-indigo-300 font-bold uppercase">
                        {result.financial_summary?.pricing_multiplier ? `${result.financial_summary.pricing_multiplier}x` : '1.0x'}
                    </span>
                </div>
                <div className="w-px h-8 bg-white/10 hidden sm:block" />
                <div className="flex flex-col gap-0.5 sm:flex">
                    <span className="mono-label">Audit Impact</span>
                    <span className={`text-sm font-bold ${delta > 0 ? 'text-success' : delta < 0 ? 'text-danger' : 'text-slate-400'}`}>
                        {delta !== 0 ? formatCurrency(delta) : '—'}
                    </span>
                </div>
                {/* Document source badge — shown only for PDF uploads (Phase 6A) */}
                {result.document_source === 'pdf_upload' && (
                    <>
                        <div className="w-px h-8 bg-white/10 hidden sm:block" />
                        <div className="flex flex-col gap-0.5 sm:flex">
                            <span className="mono-label">Source</span>
                            {result.ocr_used ? (
                                <span className="flex items-center gap-1 text-xs font-mono text-amber-400">
                                    <ScanText className="w-3 h-3" />
                                    OCR Extracted
                                </span>
                            ) : (
                                <span className="flex items-center gap-1 text-xs font-mono text-slate-300">
                                    <FileText className="w-3 h-3" />
                                    Digital PDF
                                </span>
                            )}
                        </div>
                    </>
                )}
                <div className="ml-auto">
                    <button
                        onClick={onReanalyze}
                        className="flex items-center gap-2 text-xs text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg border border-white/10 hover:border-white/20"
                    >
                        <RotateCcw className="w-3 h-3" />
                        New Analysis
                    </button>
                </div>
            </div>

            {/* ── Claim Submission Bar ── */}
            <div className="glass-card px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-l-2 border-indigo-500">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-indigo-500/10 flex items-center justify-center text-indigo-400">
                        <Landmark className="w-4 h-4" />
                    </div>
                    <div>
                        <h3 className="text-sm font-bold text-white leading-tight">Post-Coding Payer Workflow</h3>
                        <p className="text-xs text-slate-400 mt-0.5">Finalize this case and submit the charges to the payer for adjudication.</p>
                    </div>
                </div>
                
                <div className="flex items-center gap-3">
                    {submitSuccess ? (
                        <div className="flex items-center gap-2 text-sm font-bold text-success px-4 py-2 bg-success/10 rounded-lg border border-success/20">
                            <CheckCircle2 className="w-4 h-4" />
                            Claim Submitted to Payer Inbox!
                        </div>
                    ) : (
                        <>
                            <select 
                                value={selectedPayer}
                                onChange={(e) => setSelectedPayer(e.target.value)}
                                className="bg-slate-900 border border-white/10 text-slate-300 text-xs rounded-lg px-3 py-2 outline-none focus:border-indigo-500 transition-colors"
                            >
                                {payers.map(p => (
                                    <option key={p.id} value={p.id}>{p.name} ({p.payer_type})</option>
                                ))}
                            </select>
                            
                            <button
                                onClick={handleSubmitClaim}
                                disabled={isSubmitting || !selectedPayer}
                                className="flex items-center gap-2 bg-indigo-500 hover:bg-indigo-400 text-white text-xs font-bold px-4 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_15px_rgba(99,102,241,0.3)] shadow-indigo-500"
                            >
                                {isSubmitting ? 'Submitting...' : 'Submit Claim'}
                                {!isSubmitting && <Send className="w-3.5 h-3.5" />}
                            </button>
                        </>
                    )}
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

            {/* ── Row 2: Multi-code list + CPT List ── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <MultiCodeList codes={result.icd_codes} />
                <CptCodeList codes={result.cpt_codes} />
            </div>

            {/* ── Row 2.5: Candidate chart ── */}
            <div className="grid grid-cols-1 gap-6">
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

            {/* ── Row 5: Analysis metadata ── */}
            <div className="glass-card px-6 py-4 flex flex-wrap gap-6 items-center">
                <ShieldCheck className="w-4 h-4 text-slate-600" />
                <div className="flex flex-col gap-0.5">
                    <span className="mono-label">Analysis Engine</span>
                    <span className="text-xs font-mono text-slate-300">Clinical Intelligence v2</span>
                </div>
                <div className="flex flex-col gap-0.5">
                    <span className="mono-label">Code Standard</span>
                    <span className="text-xs font-mono text-slate-300">
                        {result.extraction_metadata?.icd_version ?? 'ICD-10-CM-2024'}
                    </span>
                </div>
                <div className="flex flex-col gap-0.5">
                    <span className="mono-label">Ontology Version</span>
                    <span className="text-xs font-mono text-slate-300">SNOMED-CT 2024</span>
                </div>
                <div className="flex flex-col gap-0.5">
                    <span className="mono-label">Validation Pass</span>
                    <span className="text-xs font-mono text-slate-300">
                        #{result.extraction_metadata?.attempt ?? 1}
                    </span>
                </div>
                {result.error_at && (
                    <div className="flex items-center gap-2 text-xs text-danger-light">
                        <AlertCircle className="w-3 h-3" />
                        Review required at: <span className="font-mono">{result.error_at}</span>
                    </div>
                )}
            </div>

        </div>
    );
}
