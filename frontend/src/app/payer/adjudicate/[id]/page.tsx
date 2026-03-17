'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { fetchClaimDetail, adjudicateClaim, Claim, formatCurrency } from '@/lib/api';
import { ShieldCheck, Cross, FileSignature, ArrowLeft, Activity, Info, AlertOctagon, CheckCircle2, Clock } from 'lucide-react';
import Link from 'next/link';

export default function AdjudicateClaimPage({ params }: { params: { id: string } }) {
    const router = useRouter();
    const [claim, setClaim] = useState<Claim | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [actionLoading, setActionLoading] = useState(false);
    const [denialReason, setDenialReason] = useState('');
    
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
                        
                        <div className="space-y-4">
                            <div className="bg-[#090d14]/80 p-4 rounded-xl border border-white/5">
                                <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-2">Primary ICD-10 Match</p>
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
                                                    <div className="px-3 py-1 rounded-md bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-mono font-bold text-xs">
                                                        {cpt.cpt_code}
                                                    </div>
                                                    <span className="text-sm text-slate-300">{cpt.description}</span>
                                                </div>
                                                <span className="text-sm font-mono text-amber-300 font-semibold">${cpt.cms_base_price} base</span>
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
                                    <h3 className={`font-semibold text-sm ${isRisky ? 'text-red-400' : 'text-emerald-400'}`}>Integronix Risk Score: {riskScore}/100</h3>
                                    <p className="text-xs text-slate-300 mt-1">
                                        {isRisky ? 'High risk of overcoding detected. Scrutiny recommended prior to payment.' : 'Algorithm indicates high clinical-to-code alignment. Low risk.'}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

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
                                            'bg-indigo-500'
                                        }`} />
                                        
                                        <div className="bg-slate-900/50 p-3 rounded-lg border border-white/5">
                                            <div className="flex items-center justify-between mb-1">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs font-bold text-slate-300">{log.previous_status || 'CREATED'}</span>
                                                    <span className="text-slate-500 text-[10px]">➜</span>
                                                    <span className={`text-xs font-bold ${
                                                        log.new_status === 'DENIED' ? 'text-red-400' :
                                                        log.new_status === 'PAID' ? 'text-emerald-400' :
                                                        'text-indigo-400'
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
