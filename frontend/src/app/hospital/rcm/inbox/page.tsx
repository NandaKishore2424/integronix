'use client';

import { useState, useEffect } from 'react';
import { fetchClaims, Claim, appealClaim, exportEdiUrl } from '@/lib/api';
import { useAuth } from '@/components/AuthProvider';
import { Landmark, CheckCircle2, Clock, AlertTriangle, Search, Activity, Download } from 'lucide-react';

const STATUS_CONFIG: Record<string, { color: string; icon: any; label: string }> = {
    DRAFT: { color: 'text-slate-400 bg-slate-400/10 border-slate-400/20', icon: Clock, label: 'Draft' },
    SUBMITTED: { color: 'text-auth-primary bg-auth-primary/10 border-auth-primary/20', icon: Activity, label: 'Submitted' },
    ADJUDICATING: { color: 'text-warning bg-warning/10 border-warning/20', icon: Clock, label: 'Adjudicating' },
    PAID: { color: 'text-success bg-success/10 border-success/20', icon: CheckCircle2, label: 'Paid in Full' },
    PARTIALLY_PAID: { color: 'text-indigo-400 bg-indigo-400/10 border-indigo-400/20', icon: CheckCircle2, label: 'Partially Paid' },
    DENIED: { color: 'text-danger bg-danger/10 border-danger/20', icon: AlertTriangle, label: 'Denied' },
    APPEALED: { color: 'text-orange-400 bg-orange-400/10 border-orange-400/20', icon: AlertTriangle, label: 'Appealed' },
};

function formatCurrency(amount: number) {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(amount).replace('INR', '₹');
}

export default function ClaimsInboxPage() {
    const { orgUser } = useAuth();
    const [claims, setClaims] = useState<Claim[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    
    // Appeals State
    const [appealingClaim, setAppealingClaim] = useState<Claim | null>(null);
    const [justification, setJustification] = useState('');
    const [appealLoading, setAppealLoading] = useState(false);

    // Use logged-in user's org ID — supports any tenant (Saveetha, City General, etc.)
    const orgId = orgUser?.organization_id;

    useEffect(() => {
        if (!orgId) return; // wait until auth is ready
        setLoading(true);
        fetchClaims(orgId)
            .then(data => setClaims(data))
            .catch(err => setError(err.message))
            .finally(() => setLoading(false));
    }, [orgId]);

    const handleAppeal = async () => {
        if (!appealingClaim || !justification.trim() || !orgId) return;
        setAppealLoading(true);
        try {
            await appealClaim(appealingClaim.id, justification);
            const data = await fetchClaims(orgId);
            setClaims(data);
            setAppealingClaim(null);
            setJustification('');
        } catch (err: any) {
            alert(err.message);
        } finally {
            setAppealLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex flex-col">
            {/* Header */}
            <div className="px-6 py-8 border-b border-white/[0.06]">
                <div className="max-w-7xl mx-auto flex flex-col sm:flex-row sm:items-end justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs font-semibold text-auth-primary border border-auth-primary/20 rounded-full px-3 py-1 bg-auth-primary/5 uppercase tracking-wider">
                                RCM Pipeline
                            </span>
                        </div>
                        <h1 className="text-3xl font-extrabold text-white">Claims Inbox</h1>
                        <p className="text-sm text-slate-400 mt-2 max-w-xl">
                            Track the status of your coded cases after submission to payers. Monitor adjudications, payments, and patient responsibility balances.
                        </p>
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 px-6 py-8">
                <div className="max-w-7xl mx-auto space-y-6">
                    {loading && (
                        <div className="text-center py-20 text-slate-400 text-sm font-mono animate-pulse">
                            Loading claims...
                        </div>
                    )}
                    
                    {error && (
                        <div className="glass-card p-6 flex items-center gap-3 text-danger border-danger/20">
                            <AlertTriangle className="w-5 h-5" />
                            <p className="text-sm font-medium">{error}</p>
                        </div>
                    )}

                    {!loading && !error && claims.length === 0 && (
                        <div className="glass-card p-12 flex flex-col items-center justify-center text-center">
                            <div className="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center mb-4">
                                <Landmark className="w-8 h-8 text-slate-500" />
                            </div>
                            <h3 className="text-lg font-bold text-white mb-2">No Claims Yet</h3>
                            <p className="text-sm text-slate-400 max-w-sm">
                                Complete a coding analysis and use the &quot;Submit Claim&quot; workflow in the results panel to file your first claim.
                            </p>
                        </div>
                    )}

                    {!loading && claims.length > 0 && (
                        <div className="glass-card overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full text-left border-collapse">
                                    <thead>
                                        <tr className="border-b border-white/5 bg-white/[0.02]">
                                            <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Date</th>
                                            <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Patient</th>
                                            <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Payer</th>
                                            <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider text-right">Billed</th>
                                            <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider text-right">Allowed</th>
                                            <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider text-right">Paid</th>
                                            <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider text-right">Pt. Resp</th>
                                            <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Status</th>
                                            <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider text-right">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {claims.map((claim) => {
                                            const config = STATUS_CONFIG[claim.status] || STATUS_CONFIG.DRAFT;
                                            const Icon = config.icon;
                                            return (
                                                <tr key={claim.id} className="hover:bg-white/[0.02] transition-colors group">
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                                                        {new Date(claim.created_at).toLocaleDateString()}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <div className="text-sm font-semibold text-white">{claim.patient_name}</div>
                                                        <div className="text-[10px] font-mono text-slate-500 mt-1">{claim.id.split('-')[0]}</div>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                                                        {claim.payers?.name || 'Unknown Payer'}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-right text-slate-300">
                                                        {formatCurrency(claim.total_billed_amount || 0)}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-right text-slate-400">
                                                        {claim.total_allowed_amount > 0 ? formatCurrency(claim.total_allowed_amount) : '—'}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-right font-bold text-success">
                                                        {claim.total_paid_amount > 0 ? formatCurrency(claim.total_paid_amount) : '—'}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-right text-warning">
                                                        {claim.patient_responsibility > 0 ? formatCurrency(claim.patient_responsibility) : '—'}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-[10px] font-bold uppercase tracking-wider ${config.color}`}>
                                                            <Icon className="w-3 h-3" />
                                                            {config.label}
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-right">
                                                        <div className="flex items-center justify-end gap-2">
                                                            <a 
                                                                href={exportEdiUrl(claim.id)} 
                                                                target="_blank" 
                                                                className="p-1.5 text-slate-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
                                                                title="Export EDI 837"
                                                            >
                                                                <Download className="w-4 h-4" />
                                                            </a>
                                                            {(claim.status === 'DENIED' || claim.status === 'PARTIALLY_PAID') && (
                                                                <button 
                                                                    onClick={() => setAppealingClaim(claim)}
                                                                    className="px-3 py-1.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg transition-colors"
                                                                >
                                                                    Appeal
                                                                </button>
                                                            )}
                                                        </div>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Appeal Modal Overlay */}
            {appealingClaim && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
                    <div className="bg-[#0f172a] border border-white/10 rounded-2xl p-6 w-full max-w-md shadow-2xl">
                        <h3 className="text-xl font-bold text-white mb-2">File an Appeal</h3>
                        <p className="text-sm text-slate-400 mb-4">
                            Provide clinical or administrative justification to dispute the decision for claim{' '}
                            <span className="font-mono text-slate-300">{appealingClaim.id.split('-')[0]}</span>.
                        </p>
                        <textarea 
                            value={justification}
                            onChange={e => setJustification(e.target.value)}
                            placeholder="E.g., The CPT code 58150 was entered correctly per the attached operative report..."
                            className="w-full h-32 bg-slate-900/50 border border-white/10 rounded-xl p-3 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 mb-4 resize-none"
                        />
                        <div className="flex items-center justify-end gap-3">
                            <button 
                                onClick={() => { setAppealingClaim(null); setJustification(''); }}
                                className="px-4 py-2 text-sm font-semibold text-slate-300 hover:text-white transition-colors"
                            >
                                Cancel
                            </button>
                            <button 
                                onClick={handleAppeal}
                                disabled={appealLoading || !justification.trim()}
                                className="px-4 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl transition-colors disabled:opacity-50"
                            >
                                {appealLoading ? 'Submitting...' : 'Submit Appeal'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
