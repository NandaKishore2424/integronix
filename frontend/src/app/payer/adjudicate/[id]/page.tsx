'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { fetchClaimDetail, adjudicateClaim, payerEditClaim, PayerEditPayload, Claim, formatCurrency } from '@/lib/api';
import { ShieldCheck, Cross, FileSignature, ArrowLeft, Activity, Info, AlertOctagon, CheckCircle2, Clock, FileCode2, ChevronDown, ChevronUp, Pencil, Save, X } from 'lucide-react';
import Link from 'next/link';

export default function AdjudicateClaimPage({ params }: { params: { id: string } }) {
    const router = useRouter();
    const [claim, setClaim] = useState<Claim | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [actionLoading, setActionLoading] = useState(false);
    const [denialReason, setDenialReason] = useState('');
    const [fhirExpanded, setFhirExpanded] = useState(false);

    // ── TICKET-04: Edit codes state ───────────────────────────────────────────
    const [editOpen, setEditOpen] = useState(false);
    const [editIcdCodes, setEditIcdCodes] = useState<Array<{ code: string; description: string }>>([]);
    const [editCptCodes, setEditCptCodes] = useState<Array<{ cpt_code: string; description: string }>>([]);
    const [editReason, setEditReason] = useState('');
    const [editLoading, setEditLoading] = useState(false);
    const [editSaved, setEditSaved] = useState(false);
    const [editError, setEditError] = useState('');

    useEffect(() => {
        loadClaim();
    }, [params.id]);

    const loadClaim = async () => {
        setLoading(true);
        try {
            const data = await fetchClaimDetail(params.id);
            setClaim(data);
        } catch (err) {
            console.error(err);
            setError('Failed to load Claim details.');
        } finally {
            setLoading(false);
        }
    };

    const handleAdjudicate = async (action: 'APPROVE' | 'DENY') => {
        if (!claim) return;
        if (action === 'DENY' && !denialReason.trim()) {
            alert("Please provide a denial reason.");
            return;
        }

        setActionLoading(true);
        try {
            await adjudicateClaim(claim.id, {
                action,
                payer_responsibility_pct: 0.80, // Default 80% payer coverage for demo
                denial_reason: action === 'DENY' ? denialReason : undefined
            });
            // Reload to see updated status
            await loadClaim();
            setDenialReason('');
        } catch (err: any) {
            console.error(err);
            alert(`Adjudication failed: ${err.message}`);
        } finally {
            setActionLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center p-20 text-emerald-500/50">
                <span className="animate-spin w-8 h-8 border-2 border-emerald-500/30 border-t-emerald-500 rounded-full" />
            </div>
        );
    }
    
    if (error || !claim) {
        return <div className="p-8 text-red-400">{error || 'Claim not found.'}</div>;
    }

    const claimData = (claim as any).claim_data as any || {};
    const riskScore = claimData.risk_score || 0;
    const isRisky = riskScore > 65;
    const orgName = (claim as any).organizations?.name || 'Unknown Provider';
    const gate = claimData.payer_gate_report as any || null;
    const fhirProposal = claimData.fhir_claim_proposal as any || null;
    const alreadyEdited = !!(claim as any).payer_edited;

    // Pre-fill edit state when the user opens the edit panel
    const openEditPanel = () => {
        const rawIcd: any[] = claimData.icd_codes || [];
        const rawCpt: any[] = claimData.cpt_codes || [];
        setEditIcdCodes(rawIcd.map((c: any) => ({ code: c.code || c.ai_icd_code || '', description: c.description || '' })));
        setEditCptCodes(rawCpt.map((c: any) => ({ cpt_code: c.cpt_code || c.code || '', description: c.description || '' })));
        setEditReason('');
        setEditSaved(false);
        setEditError('');
        setEditOpen(true);
    };

    const handleSaveEdits = async () => {
        if (!claim) return;
        if (!editReason.trim()) { setEditError('Please provide a reason for the code changes.'); return; }
        setEditLoading(true);
        setEditError('');
        try {
            const payload: PayerEditPayload = {
                edited_icd_codes: editIcdCodes,
                edited_cpt_codes: editCptCodes,
                edit_reason: editReason.trim(),
            };
            await payerEditClaim(claim.id, payload);
            setEditSaved(true);
            setEditOpen(false);
            await loadClaim(); // Reload to show Payer Edited badge and updated audit log
        } catch (err: any) {
            setEditError(err.message || 'Failed to save edits.');
        } finally {
            setEditLoading(false);
        }
    };


    return (
        <div className="p-8 max-w-5xl mx-auto space-y-6">
            <Link href="/payer/inbox" className="text-emerald-500 hover:text-emerald-400 text-sm font-semibold flex items-center gap-2 w-max transition-colors">
                <ArrowLeft className="w-4 h-4" /> Back to Queue
            </Link>

            <div className="flex items-start justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3 mb-1">
                        Claim <span className="text-emerald-500 font-mono text-xl uppercase tracking-widest">{claim.id.split('-')[0]}</span>
                    </h1>
                    <p className="text-slate-400">Patient: <span className="text-slate-200 font-semibold">{claim.patient_name}</span> • Provider: <span className="text-slate-200 font-semibold">{orgName}</span></p>
                </div>
                <div className="text-right">
                    <p className="text-xs text-slate-500 uppercase tracking-widest font-bold mb-1">Status</p>
                    <div className="px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 text-sm font-bold text-slate-300">
                        {claim.status}
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Standard Claim Information */}
                <div className="lg:col-span-2 space-y-6">
                    <div className="bg-slate-900/50 rounded-2xl border border-emerald-900/30 p-6">
                        <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                            <Activity className="w-5 h-5 text-emerald-500" />
                            Clinical Validation (AI Summary)
                        </h2>

                            {gate && (
                                <div className="bg-[#090d14]/80 p-4 rounded-xl border border-white/5 mb-4">
                                    <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-2">
                                        Payer Policy Gate
                                    </p>
                                    <div className="flex items-center gap-2 mb-2">
                                        <span className={`px-3 py-1 rounded-md text-xs font-bold border ${
                                            gate.gate_status === 'PASS'
                                                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                                                : 'bg-amber-500/10 text-amber-300 border-amber-500/20'
                                        }`}>
                                            {gate.gate_status === 'PASS' ? 'Auto-approve eligible' : 'Needs manual review'}
                                        </span>
                                        {gate.should_auto_approve && (
                                            <span className="text-xs font-bold text-emerald-300">(Auto decision enabled)</span>
                                        )}
                                    </div>

                                    {Array.isArray(gate.reasons) && gate.reasons.length > 0 ? (
                                        <div className="space-y-2">
                                            {gate.reasons.map((r: any, idx: number) => (
                                                <div key={`${r.code}-${idx}`} className="text-xs text-slate-300 flex gap-2">
                                                    <span className="font-mono text-amber-300 shrink-0">{r.code}</span>
                                                    <span className="text-slate-300">{r.message}</span>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <div className="text-xs text-slate-400">No issues detected by payer policy.</div>
                                    )}
                                </div>
                            )}
                        
                        <div className="space-y-4">
                            <div className="bg-[#090d14]/80 p-4 rounded-xl border border-white/5">
                                <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-2">
                                    Primary {(claimData.icd_codes?.[0]?.mapping_path ?? '').includes('icd11') ? 'ICD-11' : 'ICD-10'} Diagnosis
                                </p>
                                {claimData.icd_codes && claimData.icd_codes.length > 0 ? (
                                    <div className="flex items-center gap-3">
                                        <div className="px-3 py-1 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono font-bold">
                                            {claimData.icd_codes[0].code}
                                        </div>
                                        <span className="text-sm text-slate-300 font-medium">{claimData.icd_codes[0].description}</span>
                                    </div>
                                ) : (
                                    <span className="text-sm font-mono text-slate-500">No diagnoses coded.</span>
                                )}
                            </div>

                            <div className="bg-[#090d14]/80 p-4 rounded-xl border border-white/5">
                                <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-2">Billed Procedures (CPT)</p>
                                {claimData.cpt_codes && claimData.cpt_codes.length > 0 ? (
                                    <div className="space-y-3">
                                        {claimData.cpt_codes.map((cpt: any, idx: number) => (
                                            <div key={idx} className="flex items-center justify-between">
                                                <div className="flex items-center gap-3">
                                                    <div className="px-3 py-1 rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20 font-mono font-bold text-xs">
                                                        {cpt.cpt_code}
                                                    </div>
                                                    <span className="text-sm text-slate-300">{cpt.description}</span>
                                                </div>
                                                <span className="text-sm font-mono text-amber-300 font-semibold">
                                                        ₹{((cpt.gross_charge ?? cpt.cms_base_price ?? 0)).toLocaleString('en-IN', { maximumFractionDigits: 2 })} billed
                                                    </span>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <span className="text-sm font-mono text-slate-500">No procedures coded.</span>
                                )}
                            </div>
                            
                            <div className={`p-4 rounded-xl border flex gap-3 items-start ${isRisky ? 'bg-red-500/10 border-red-500/20' : 'bg-emerald-500/10 border-emerald-500/20'}`}>
                                {isRisky ? <AlertOctagon className="w-5 h-5 text-red-500 shrink-0 mt-0.5" /> : <ShieldCheck className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />}
                                <div>
                                    <h3 className={`font-semibold text-sm ${isRisky ? 'text-red-400' : 'text-emerald-400'}`}>
                                        Integronix Risk Score: {Math.round(riskScore * 100)}%
                                    </h3>
                                    <p className="text-xs text-slate-300 mt-1">
                                        {isRisky ? 'High risk of overcoding detected. Scrutiny recommended prior to payment.' : 'Algorithm indicates high clinical-to-code alignment. Low risk.'}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* FHIR Claim Proposal */}
                    {fhirProposal && (
                        <div className="bg-slate-900/50 rounded-2xl border border-amber-900/30 p-6">
                            <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                                <FileCode2 className="w-5 h-5 text-amber-400" />
                                FHIR Claim Proposal
                                <span className="ml-auto text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                    Hospital Proposed
                                </span>
                            </h2>

                            {/* Summary rows */}
                            <div className="space-y-3 mb-4">
                                {/* Patient */}
                                <div className="bg-[#090d14]/80 p-3 rounded-xl border border-white/5">
                                    <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-1.5">Patient</p>
                                    {(() => {
                                        const contained = fhirProposal.contained?.[0];
                                        const nameText = contained?.name?.[0]?.text;
                                        const dob = contained?.birthDate;
                                        const gender = contained?.gender;
                                        return (
                                            <div className="flex flex-wrap gap-3 text-sm">
                                                <span className="text-slate-200 font-semibold">{nameText || <span className="text-slate-500 italic">Not documented</span>}</span>
                                                {dob && <span className="text-slate-400">DOB: {dob}</span>}
                                                {gender && <span className="text-slate-400 capitalize">{gender}</span>}
                                            </div>
                                        );
                                    })()}
                                </div>

                                {/* Diagnoses */}
                                <div className="bg-[#090d14]/80 p-3 rounded-xl border border-white/5">
                                    <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-1.5">
                                        Diagnoses&nbsp;
                                        <span className="text-amber-400 normal-case font-normal">
                                            ({fhirProposal.extension?.find((e: any) => e.url?.includes('icd-version'))?.valueString || 'ICD'})
                                        </span>
                                    </p>
                                    <div className="space-y-1.5">
                                        {(fhirProposal.diagnosis || []).map((d: any, idx: number) => (
                                            <div key={idx} className="flex items-center gap-2 text-sm">
                                                <span className="font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 text-xs">
                                                    {d.diagnosisCodeableConcept?.coding?.[0]?.code}
                                                </span>
                                                <span className="text-slate-300 text-xs truncate">{d.diagnosisCodeableConcept?.coding?.[0]?.display}</span>
                                                {idx === 0 && <span className="text-[10px] text-slate-500 ml-auto shrink-0">principal</span>}
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Procedures */}
                                {(fhirProposal.item || []).length > 0 && (
                                    <div className="bg-[#090d14]/80 p-3 rounded-xl border border-white/5">
                                        <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-1.5">Procedures (CPT)</p>
                                        <div className="space-y-1.5">
                                            {fhirProposal.item.map((item: any, idx: number) => (
                                                <div key={idx} className="flex items-center justify-between text-sm">
                                                    <div className="flex items-center gap-2">
                                                        <span className="font-mono px-2 py-0.5 rounded bg-slate-700/60 text-slate-300 border border-white/5 text-xs">
                                                            {item.productOrService?.coding?.[0]?.code}
                                                        </span>
                                                        <span className="text-slate-400 text-xs truncate max-w-[200px]">{item.productOrService?.coding?.[0]?.display}</span>
                                                    </div>
                                                    <span className="text-amber-300 font-mono text-xs shrink-0">
                                                        ₹{item.net?.value?.toLocaleString('en-IN') ?? '—'}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Total */}
                                <div className="flex items-center justify-between text-sm px-1">
                                    <span className="text-slate-400">Proposed Total (Hospital Billed)</span>
                                    <span className="font-mono font-bold text-amber-300">
                                        ₹{fhirProposal.total?.value?.toLocaleString('en-IN') ?? '—'}
                                    </span>
                                </div>
                            </div>

                            {/* Collapsible raw JSON viewer */}
                            <button
                                onClick={() => setFhirExpanded(v => !v)}
                                className="flex items-center gap-2 text-xs text-slate-400 hover:text-amber-300 transition-colors font-semibold"
                            >
                                {fhirExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                                {fhirExpanded ? 'Hide raw FHIR JSON' : 'View raw FHIR Claim JSON'}
                            </button>
                            {fhirExpanded && (
                                <pre className="mt-3 bg-[#060a10] text-[10px] leading-relaxed text-emerald-300/80 font-mono p-4 rounded-xl border border-white/5 overflow-auto max-h-96 whitespace-pre-wrap break-all">
                                    {JSON.stringify(fhirProposal, null, 2)}
                                </pre>
                            )}
                        </div>
                    )}
                </div>

                    {/* ── TICKET-04: Payer Edit Codes Panel ── */}
                    {claim.status === 'SUBMITTED' && (
                        <div className="bg-slate-900/50 rounded-2xl border border-amber-900/30 p-6">
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                                    <Pencil className="w-5 h-5 text-amber-400" />
                                    Edit Codes
                                    {alreadyEdited && (
                                        <span className="ml-2 text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                            Payer Edited
                                        </span>
                                    )}
                                </h2>
                                {!editOpen ? (
                                    <button
                                        onClick={openEditPanel}
                                        className="flex items-center gap-1.5 text-xs font-semibold text-amber-400 hover:text-amber-300 border border-amber-500/20 bg-amber-500/5 hover:bg-amber-500/10 rounded-lg px-3 py-1.5 transition-all"
                                    >
                                        <Pencil className="w-3 h-3" /> {alreadyEdited ? 'Edit Again' : 'Edit Codes'}
                                    </button>
                                ) : (
                                    <button
                                        onClick={() => setEditOpen(false)}
                                        className="flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-slate-300 transition-colors"
                                    >
                                        <X className="w-3.5 h-3.5" /> Cancel
                                    </button>
                                )}
                            </div>

                            {!editOpen ? (
                                <p className="text-xs text-slate-400">
                                    {alreadyEdited
                                        ? `Previously edited. Reason: "${(claim as any).payer_edit_reason}"`
                                        : 'If the hospital-proposed codes are incorrect, click Edit Codes to correct them before approving or denying.'}
                                </p>
                            ) : (
                                <div className="space-y-4">
                                    {/* ICD Code Rows */}
                                    {editIcdCodes.length > 0 && (
                                        <div>
                                            <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-2">Diagnosis Codes (ICD)</p>
                                            <div className="space-y-2">
                                                {editIcdCodes.map((icd, idx) => (
                                                    <div key={idx} className="flex gap-2 items-center">
                                                        <input
                                                            className="w-32 bg-slate-800 border border-white/10 rounded-lg px-2 py-1.5 text-xs font-mono text-amber-300 focus:border-amber-400 outline-none"
                                                            value={icd.code}
                                                            onChange={e => {
                                                                const next = [...editIcdCodes];
                                                                next[idx] = { ...next[idx], code: e.target.value };
                                                                setEditIcdCodes(next);
                                                            }}
                                                            placeholder="ICD code"
                                                        />
                                                        <input
                                                            className="flex-1 bg-slate-800 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-slate-300 focus:border-amber-400 outline-none"
                                                            value={icd.description}
                                                            onChange={e => {
                                                                const next = [...editIcdCodes];
                                                                next[idx] = { ...next[idx], description: e.target.value };
                                                                setEditIcdCodes(next);
                                                            }}
                                                            placeholder="Description"
                                                        />
                                                        <button
                                                            onClick={() => setEditIcdCodes(prev => prev.filter((_, i) => i !== idx))}
                                                            className="p-1.5 rounded-lg text-red-400/60 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                                                        >
                                                            <X className="w-3.5 h-3.5" />
                                                        </button>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* CPT Code Rows */}
                                    {editCptCodes.length > 0 && (
                                        <div>
                                            <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-2">Procedure Codes (CPT)</p>
                                            <div className="space-y-2">
                                                {editCptCodes.map((cpt, idx) => (
                                                    <div key={idx} className="flex gap-2 items-center">
                                                        <input
                                                            className="w-24 bg-slate-800 border border-white/10 rounded-lg px-2 py-1.5 text-xs font-mono text-amber-300 focus:border-amber-400 outline-none"
                                                            value={cpt.cpt_code}
                                                            onChange={e => {
                                                                const next = [...editCptCodes];
                                                                next[idx] = { ...next[idx], cpt_code: e.target.value };
                                                                setEditCptCodes(next);
                                                            }}
                                                            placeholder="CPT code"
                                                        />
                                                        <input
                                                            className="flex-1 bg-slate-800 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-slate-300 focus:border-amber-400 outline-none"
                                                            value={cpt.description}
                                                            onChange={e => {
                                                                const next = [...editCptCodes];
                                                                next[idx] = { ...next[idx], description: e.target.value };
                                                                setEditCptCodes(next);
                                                            }}
                                                            placeholder="Description"
                                                        />
                                                        <button
                                                            onClick={() => setEditCptCodes(prev => prev.filter((_, i) => i !== idx))}
                                                            className="p-1.5 rounded-lg text-red-400/60 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                                                        >
                                                            <X className="w-3.5 h-3.5" />
                                                        </button>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Reason (required) */}
                                    <div>
                                        <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-1.5">Reason for Edit <span className="text-red-400">*</span></p>
                                        <textarea
                                            rows={2}
                                            className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-xs text-slate-200 focus:border-amber-400 outline-none resize-none"
                                            placeholder="Explain why these codes were changed..."
                                            value={editReason}
                                            onChange={e => setEditReason(e.target.value)}
                                        />
                                    </div>

                                    {editError && <p className="text-xs text-red-400">{editError}</p>}

                                    <button
                                        onClick={handleSaveEdits}
                                        disabled={editLoading || !editReason.trim()}
                                        className="w-full flex items-center justify-center gap-2 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/20 font-bold px-4 py-2.5 rounded-xl text-sm transition-all disabled:opacity-50"
                                    >
                                        <Save className="w-4 h-4" />
                                        {editLoading ? 'Saving...' : 'Save Code Edits'}
                                    </button>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Financials & Action Panel */}
                <div className="space-y-6">
                    <div className="bg-slate-900/50 rounded-2xl border border-emerald-900/30 p-6">
                        <h2 className="text-lg font-bold text-white mb-4">Financials</h2>
                        
                        <div className="space-y-4">
                            <div className="flex justify-between items-center text-sm">
                                <span className="text-slate-400 font-medium">Hospital Billed</span>
                                <span className="font-mono font-bold text-amber-300 text-lg">{formatCurrency(claim.total_billed_amount)}</span>
                            </div>
                            <div className="flex justify-between items-center text-sm">
                                <span className="text-slate-400 font-medium group relative cursor-help">
                                    Payer Allowed
                                    <div className="absolute top-6 -left-2 w-48 bg-slate-800 border border-white/10 p-2 text-[10px] text-slate-300 rounded shadow-xl opacity-0 group-hover:opacity-100 transition-opacity z-10 pointer-events-none">
                                        Calculated based on your active fee-schedule contract with this provider.
                                    </div>
                                </span>
                                <span className="font-mono font-bold text-emerald-400 text-lg">
                                    {claim.status === 'SUBMITTED' ? '(Pending Adjudication)' : formatCurrency(claim.total_allowed_amount)}
                                </span>
                            </div>
                            
                            {claim.status !== 'SUBMITTED' && claim.status !== 'DRAFT' && (
                                <div className="pt-4 mt-4 border-t border-white/10 space-y-3">
                                    <div className="flex justify-between items-center text-[13px]">
                                        <span className="text-slate-400">Payer Responsibility (80%)</span>
                                        <span className="font-mono font-semibold text-emerald-300">{formatCurrency(claim.total_paid_amount)}</span>
                                    </div>
                                    <div className="flex justify-between items-center text-[13px]">
                                        <span className="text-slate-400">Patient Owes (20%)</span>
                                        <span className="font-mono font-semibold text-slate-300">{formatCurrency(claim.patient_responsibility)}</span>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Adjudication Controls - Only show if currently SUBMITTED */}
                    {claim.status === 'SUBMITTED' ? (
                        <div className="bg-[#090d14] rounded-2xl border border-emerald-900/50 p-6">
                            <h2 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                                <FileSignature className="w-4 h-4 text-emerald-500" />
                                Adjudication Actions
                            </h2>
                            <div className="space-y-3">
                                <button 
                                    onClick={() => handleAdjudicate('APPROVE')} disabled={actionLoading}
                                    className="w-full flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-4 py-3 rounded-xl transition-all disabled:opacity-50"
                                >
                                    <CheckCircle2 className="w-4 h-4" /> Approve (Pay Contract Rate)
                                </button>
                                
                                <div className="pt-4 border-t border-white/5 space-y-3">
                                    <input 
                                        type="text" placeholder="Reason for denial..." 
                                        value={denialReason} onChange={e => setDenialReason(e.target.value)}
                                        className="w-full bg-slate-900/50 border border-white/10 rounded-lg py-2 px-3 text-sm text-slate-200 focus:border-red-500 outline-none"
                                    />
                                    <button 
                                        onClick={() => handleAdjudicate('DENY')} disabled={actionLoading || !denialReason.trim()}
                                        className="w-full flex items-center justify-center gap-2 bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/20 font-bold px-4 py-2.5 rounded-xl transition-all disabled:opacity-50"
                                    >
                                        <AlertOctagon className="w-4 h-4" /> Deny Claim
                                    </button>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="bg-emerald-900/10 border border-emerald-500/20 rounded-2xl p-6 flex flex-col items-center justify-center text-center gap-3">
                            <ShieldCheck className="w-8 h-8 text-emerald-500/50" />
                            <div>
                                <h3 className="text-emerald-400 font-semibold mb-1">Adjudication Complete</h3>
                                <p className="text-xs text-slate-400">This claim has already been processed by the engine and returned to the hospital.</p>
                            </div>
                        </div>
                    )}
                    
                    {/* HIPAA Audit Trail */}
                    {claim.claim_audit_logs && claim.claim_audit_logs.length > 0 && (
                        <div className="bg-[#090d14] rounded-2xl border border-white/5 p-6">
                            <h2 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                                <Clock className="w-4 h-4 text-slate-400" />
                                Claim History & Audit Log
                            </h2>
                            <div className="space-y-4">
                                {claim.claim_audit_logs.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()).map((log, idx) => (
                                    <div key={log.id} className="relative pl-6">
                                        {/* Timeline Line */}
                                        {idx !== claim.claim_audit_logs!.length - 1 && (
                                            <div className="absolute left-2.5 top-5 bottom-[-20px] w-0.5 bg-white/5" />
                                        )}
                                        {/* Timeline Dot */}
                                        <div className={`absolute left-1.5 top-1.5 w-2.5 h-2.5 rounded-full border-2 border-[#090d14] ${
                                            log.new_status === 'DENIED' ? 'bg-red-500' :
                                            log.new_status === 'PAID' ? 'bg-emerald-500' :
                                            'bg-amber-500'
                                        }`} />
                                        
                                        <div className="bg-slate-900/50 p-3 rounded-lg border border-white/5">
                                            <div className="flex items-center justify-between mb-1">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs font-bold text-slate-300">{log.previous_status || 'CREATED'}</span>
                                                    <span className="text-slate-500 text-[10px]">➜</span>
                                                    <span className={`text-xs font-bold ${
                                                        log.new_status === 'DENIED' ? 'text-red-400' :
                                                        log.new_status === 'PAID' ? 'text-emerald-400' :
                                                        'text-amber-400'
                                                    }`}>{log.new_status}</span>
                                                </div>
                                                <span className="text-[10px] text-slate-500">
                                                    {new Date(log.created_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                                                </span>
                                            </div>
                                            {log.action_notes && (
                                                <p className="text-xs text-slate-400 mt-1.5">{log.action_notes}</p>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
