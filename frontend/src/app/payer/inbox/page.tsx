'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { fetchPayerByOrg, fetchPayerClaims, Claim, formatCurrency } from '@/lib/api';
import { Inbox, FileSignature, AlertCircle, RefreshCw, Building2, Search } from 'lucide-react';
import { useAuth } from '@/components/AuthProvider';

export default function PayerInboxPage() {
    const router = useRouter();
    const { orgUser } = useAuth();
    const [claims, setClaims] = useState<Claim[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [filterStatus, setFilterStatus] = useState<string>('SUBMITTED');

    useEffect(() => {
        if (orgUser?.organization_id) loadInbox();
    }, [orgUser]);

    const loadInbox = async () => {
        setLoading(true);
        setError('');
        try {
            // Resolve the payer whose name matches the logged-in user's organization.
            // Nathin (Global Health Insurance org) → Global Health Insurance payer record.
            const payer = await fetchPayerByOrg(orgUser!.organization_id);
            if (!payer) {
                setError('No payer record found for your organization. Check your account setup.');
                return;
            }
            const data = await fetchPayerClaims(payer.id);
            setClaims(data);
        } catch (err) {
            console.error(err);
            setError('Failed to load payer global inbox. Is the backend running?');
        } finally {
            setLoading(false);
        }
    };

    const STATUS_UI = {
        'SUBMITTED': { label: 'Awaiting Review', styling: 'text-amber-400 bg-amber-500/10 border-amber-500/20' },
        'PAID': { label: 'Paid - Clean', styling: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' },
        'PARTIALLY_PAID': { label: 'Adjudicated/Adjusted', styling: 'text-blue-400 bg-blue-500/10 border-blue-500/20' },
        'DENIED': { label: 'Denied', styling: 'text-red-400 bg-red-500/10 border-red-500/20' },
        'DRAFT': { label: 'Hospital Draft', styling: 'text-slate-400 bg-slate-500/10 border-slate-500/20' }
    } as any;

    const filteredClaims = claims.filter(c => filterStatus === 'ALL' || c.status === filterStatus);

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
                        <Inbox className="w-8 h-8 text-emerald-500" />
                        Global Claims Queue
                    </h1>
                    <p className="text-slate-400 mt-1 flex items-center gap-2">
                        <AlertCircle className="w-4 h-4" />
                        Review inbound Hospital claims, run automated risk checks, and adjudicate payments.
                    </p>
                </div>
                <button
                    onClick={loadInbox} disabled={loading}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
                >
                    <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    Refresh Inbox
                </button>
            </div>

            <div className="flex gap-4 items-center">
                <div className="relative flex-1 max-w-md">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <input 
                        type="text" placeholder="Search claim IDs or Patient names..."
                        className="w-full bg-slate-900/50 border border-emerald-900/40 rounded-xl py-2.5 pl-10 pr-4 text-sm text-slate-200 outline-none focus:border-emerald-500"
                    />
                </div>
                <div className="flex bg-slate-900/50 rounded-lg p-1 border border-emerald-900/40">
                    {['ALL', 'SUBMITTED', 'PAID', 'DENIED'].map(s => (
                        <button
                            key={s} onClick={() => setFilterStatus(s)}
                            className={`px-4 py-1.5 text-xs font-bold rounded-md transition-colors ${filterStatus === s ? 'bg-emerald-500 text-white shadow-md' : 'text-slate-500 hover:text-slate-300'}`}
                        >
                            {s}
                        </button>
                    ))}
                </div>
            </div>

            {error ? (
                <div className="bg-red-500/10 border border-red-500/20 p-6 rounded-xl flex items-start gap-4">
                    <AlertCircle className="w-6 h-6 text-red-500 shrink-0" />
                    <div>
                        <h3 className="text-red-400 font-semibold">Inbox Error</h3>
                        <p className="text-slate-300 text-sm mt-1">{error}</p>
                    </div>
                </div>
            ) : loading ? (
                <div className="h-64 flex flex-col items-center justify-center gap-4 text-emerald-500/50">
                    <RefreshCw className="w-8 h-8 animate-spin" />
                    <span className="text-sm font-medium">Fetching inbound transactions...</span>
                </div>
            ) : (
                <div className="bg-slate-900/50 rounded-2xl border border-emerald-900/30 overflow-hidden shadow-2xl">
                    <table className="w-full text-left text-sm whitespace-nowrap">
                        <thead className="bg-[#090d14]/80 text-emerald-500/80 text-xs uppercase tracking-wider font-semibold border-b border-emerald-900/30">
                            <tr>
                                <th className="px-6 py-4">Status</th>
                                <th className="px-6 py-4">Claim ID</th>
                                <th className="px-6 py-4">Date Filed</th>
                                <th className="px-6 py-4">Origin Hospital</th>
                                <th className="px-6 py-4">Patient</th>
                                <th className="px-6 py-4 text-right">Requested Billed</th>
                                <th className="px-6 py-4"></th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-emerald-900/20 text-slate-300">
                            {filteredClaims.length === 0 ? (
                                <tr>
                                    <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                                        <div className="flex flex-col items-center gap-2">
                                            <Inbox className="w-8 h-8 opacity-20" />
                                            <span>No claims found in your inbox queue.</span>
                                        </div>
                                    </td>
                                </tr>
                            ) : filteredClaims.map(claim => {
                                const ui = STATUS_UI[claim.status] || STATUS_UI['DRAFT'];
                                const orgName = (claim as any).organizations?.name || 'Unknown Provider';
                                
                                return (
                                    <tr key={claim.id} className="hover:bg-emerald-900/10 transition-colors group">
                                        <td className="px-6 py-4">
                                            <span className={`px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider rounded-lg border ${ui.styling}`}>
                                                {ui.label}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 font-mono text-xs">{claim.id.split('-')[0]}...</td>
                                        <td className="px-6 py-4 font-mono text-xs text-slate-400">
                                            {new Date(claim.created_at).toLocaleDateString()}
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-2">
                                                <Building2 className="w-4 h-4 text-emerald-500/50" />
                                                <span className="font-semibold text-white">{orgName}</span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">{claim.patient_name}</td>
                                        <td className="px-6 py-4 text-right font-mono font-bold text-amber-300">
                                            {formatCurrency(claim.total_billed_amount)}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <button
                                                onClick={() => router.push(`/payer/adjudicate/${claim.id}`)}
                                                className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-2 ml-auto text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 px-3 py-1.5 rounded-lg"
                                            >
                                                <FileSignature className="w-3.5 h-3.5" />
                                                Review Case
                                            </button>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
