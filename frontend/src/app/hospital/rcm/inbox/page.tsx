'use client';

import { useState, useEffect } from 'react';
import { fetchClaims, Claim, appealClaim, downloadEdi, type EdiKind } from '@/lib/api';
import { useAuth } from '@/components/AuthProvider';
import { motion } from 'framer-motion';
import { Landmark, CheckCircle2, Clock, AlertTriangle, Activity, FileDown } from 'lucide-react';

const STATUS_CONFIG: Record<string, { color: string; icon: any; label: string }> = {
    DRAFT: { color: 'text-slate-400 bg-slate-400/10 border-slate-400/20', icon: Clock, label: 'Draft' },
    SUBMITTED: { color: 'text-auth-primary bg-auth-primary/10 border-auth-primary/20', icon: Activity, label: 'Submitted' },
    ADJUDICATING: { color: 'text-warning bg-warning/10 border-warning/20', icon: Clock, label: 'Adjudicating' },
    PAID: { color: 'text-success bg-success/10 border-success/20', icon: CheckCircle2, label: 'Paid in Full' },
    PARTIALLY_PAID: { color: 'text-amber-400 bg-amber-400/10 border-amber-400/20', icon: CheckCircle2, label: 'Partially Paid' },
    DENIED: { color: 'text-danger bg-danger/10 border-danger/20', icon: AlertTriangle, label: 'Denied' },
    APPEALED: { color: 'text-orange-400 bg-orange-400/10 border-orange-400/20', icon: AlertTriangle, label: 'Appealed' },
};

type FilterKey = 'all' | 'open' | 'settled' | 'disputed';

const FILTERS: { key: FilterKey; label: string; statuses: string[] }[] = [
    { key: 'all', label: 'All', statuses: [] },
    { key: 'open', label: 'Awaiting payer', statuses: ['DRAFT', 'SUBMITTED', 'ADJUDICATING'] },
    { key: 'settled', label: 'Paid', statuses: ['PAID', 'PARTIALLY_PAID'] },
    { key: 'disputed', label: 'Denied or appealed', statuses: ['DENIED', 'APPEALED'] },
];

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
    const [filter, setFilter] = useState<FilterKey>('all');

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

    const counts = {
        all: claims.length,
        open: claims.filter((c) => FILTERS[1].statuses.includes(c.status)).length,
        settled: claims.filter((c) => FILTERS[2].statuses.includes(c.status)).length,
        disputed: claims.filter((c) => FILTERS[3].statuses.includes(c.status)).length,
    };
    const visible = claims.filter((c) => filter === 'all' || FILTERS.find((f) => f.key === filter)!.statuses.includes(c.status));
    const totals = claims.reduce(
        (t, c) => ({
            billed: t.billed + (c.total_billed_amount || 0),
            paid: t.paid + (c.total_paid_amount || 0),
            patient: t.patient + (c.patient_responsibility || 0),
        }),
        { billed: 0, paid: 0, patient: 0 },
    );

    return (
        <div className="min-h-screen flex flex-col">
            {/* Header */}
            <div className="px-6 py-8 border-b border-white/[0.06]">
                <div className="max-w-6xl mx-auto">
                    <span className="text-xs font-semibold text-auth-primary border border-auth-primary/20 rounded-full px-3 py-1 bg-auth-primary/5 uppercase tracking-wider">
                        RCM Pipeline
                    </span>
                    <h1 className="text-3xl font-extrabold text-white mt-3">Claims Inbox</h1>
                    <p className="text-sm text-slate-400 mt-2 max-w-xl">
                        Every claim your organisation has sent to a payer: what was billed, what the payer allowed and paid,
                        and what the patient owes.
                    </p>

                    {!loading && claims.length > 0 && (
                        <dl className="mt-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
                            <SummaryStat label="Claims" value={String(claims.length)} hint={`${counts.open} awaiting the payer`} />
                            <SummaryStat label="Billed" value={formatCurrency(totals.billed)} />
                            <SummaryStat label="Collected from payers" value={formatCurrency(totals.paid)} tone="text-success" />
                            <SummaryStat label="Patient balances" value={formatCurrency(totals.patient)} tone="text-warning" />
                        </dl>
                    )}
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 px-6 py-8">
                <div className="max-w-6xl mx-auto space-y-5">
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
                        <>
                            <div className="flex flex-wrap gap-2" role="tablist" aria-label="Filter claims">
                                {FILTERS.map((f) => (
                                    <button
                                        key={f.key}
                                        role="tab"
                                        aria-selected={filter === f.key}
                                        onClick={() => setFilter(f.key)}
                                        className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors ${
                                            filter === f.key
                                                ? 'border-amber-500/50 bg-amber-500/15 text-amber-300'
                                                : 'border-white/10 text-slate-400 hover:border-white/25 hover:text-white'
                                        }`}
                                    >
                                        {f.label}
                                        <span className="ml-2 font-mono text-xs opacity-70">{counts[f.key]}</span>
                                    </button>
                                ))}
                            </div>

                            <motion.ul
                                key={filter}
                                className="space-y-3"
                                initial="hidden"
                                animate="shown"
                                variants={{ hidden: {}, shown: { transition: { staggerChildren: 0.05 } } }}
                            >
                                {visible.map((claim) => (
                                    <ClaimRow key={claim.id} claim={claim} onAppeal={() => setAppealingClaim(claim)} />
                                ))}
                                {visible.length === 0 && (
                                    <li className="glass-card p-8 text-center text-sm text-slate-400">No claims in this view.</li>
                                )}
                            </motion.ul>
                        </>
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
                            className="w-full h-32 bg-slate-900/50 border border-white/10 rounded-xl p-3 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-amber-500 mb-4 resize-none"
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
                                className="px-4 py-2 text-sm font-semibold text-white bg-amber-500 hover:bg-amber-500 rounded-xl transition-colors disabled:opacity-50"
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

function SummaryStat({ label, value, hint, tone = 'text-white' }: { label: string; value: string; hint?: string; tone?: string }) {
    return (
        <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] px-4 py-3">
            <dt className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</dt>
            <dd className={`mt-1 font-mono text-xl font-bold ${tone}`}>{value}</dd>
            {hint && <dd className="mt-0.5 text-xs text-slate-500">{hint}</dd>}
        </div>
    );
}

function Amount({ label, value, tone = 'text-slate-200' }: { label: string; value: number | null; tone?: string }) {
    return (
        <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
            <p className={`mt-0.5 font-mono text-sm font-semibold ${value ? tone : 'text-slate-600'}`}>
                {value ? formatCurrency(value) : '—'}
            </p>
        </div>
    );
}

/** A download button whose explanation appears only when this button itself is hovered or focused. */
function EdiLink({ claimId, kind, label, title, detail }: { claimId: string; kind: EdiKind; label: string; title: string; detail: string }) {
    const [busy, setBusy] = useState(false);
    const download = async () => {
        setBusy(true);
        try {
            await downloadEdi(claimId, kind);
        } catch (err: any) {
            alert(`Could not download the ${kind} file: ${err.message}`);
        } finally {
            setBusy(false);
        }
    };
    return (
        <span className="relative group/tip">
            <button
                type="button"
                onClick={download}
                disabled={busy}
                className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-white/25 hover:text-white disabled:opacity-60"
            >
                <FileDown className="h-3.5 w-3.5" />
                {busy ? 'Preparing…' : label}
            </button>
            <span
                role="tooltip"
                className="pointer-events-none invisible absolute bottom-full right-0 z-20 mb-2 w-60 rounded-lg border border-slate-700 bg-slate-900 p-3 text-left text-xs leading-relaxed text-slate-300 opacity-0 shadow-xl transition-opacity group-hover/tip:visible group-hover/tip:opacity-100 group-focus-within/tip:visible group-focus-within/tip:opacity-100"
            >
                <strong className="mb-1 block text-white">{title}</strong>
                {detail}
            </span>
        </span>
    );
}

function ClaimRow({ claim, onAppeal }: { claim: Claim; onAppeal: () => void }) {
    const config = STATUS_CONFIG[claim.status] || STATUS_CONFIG.DRAFT;
    const Icon = config.icon;
    const allowed = claim.total_allowed_amount || 0;
    const paid = claim.total_paid_amount || 0;
    const patient = claim.patient_responsibility || 0;
    const paidPct = allowed > 0 ? (paid / allowed) * 100 : 0;
    const patientPct = allowed > 0 ? (patient / allowed) * 100 : 0;
    const adjudicated = ['PAID', 'PARTIALLY_PAID', 'DENIED'].includes(claim.status);

    return (
        <motion.li
            variants={{ hidden: { opacity: 0, y: 12 }, shown: { opacity: 1, y: 0, transition: { duration: 0.3 } } }}
            className="glass-card px-5 py-4 transition-colors hover:border-white/15"
        >
            <div className="grid gap-4 lg:grid-cols-12 lg:items-center">
                <div className="lg:col-span-4 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                        <p className={`truncate font-semibold ${claim.patient_name ? 'text-white' : 'italic text-slate-400'}`}>
                            {claim.patient_name || 'Patient name not recorded'}
                        </p>
                        <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${config.color}`}>
                            <Icon className="h-3 w-3" />
                            {config.label}
                        </span>
                    </div>
                    <p className="mt-1.5 text-xs text-slate-500">
                        <span className="font-mono">#{claim.id.split('-')[0]}</span>
                        {' · '}
                        {new Date(claim.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                        {' · '}
                        {claim.payers?.name || 'Unknown payer'}
                    </p>
                </div>

                <div className="lg:col-span-4">
                    <div className="grid grid-cols-4 gap-3">
                        <Amount label="Billed" value={claim.total_billed_amount} />
                        <Amount label="Allowed" value={allowed} tone="text-slate-300" />
                        <Amount label="Paid" value={paid} tone="text-success" />
                        <Amount label="Patient" value={patient} tone="text-warning" />
                    </div>
                    {allowed > 0 && (
                        <div
                            className="mt-2.5 flex h-1.5 overflow-hidden rounded-full bg-white/[0.06]"
                            title={`Payer paid ${Math.round(paidPct)}%, patient owes ${Math.round(patientPct)}% of the allowed amount`}
                        >
                            <div className="h-full bg-success" style={{ width: `${paidPct}%` }} />
                            <div className="h-full bg-warning" style={{ width: `${patientPct}%` }} />
                        </div>
                    )}
                </div>

                <div className="lg:col-span-4 flex flex-wrap items-center gap-2 lg:justify-end">
                    <EdiLink
                        claimId={claim.id}
                        kind="837"
                        label="Claim 837"
                        title="EDI 837 claim file"
                        detail="The claim as a raw ANSI X12 file, the format hospitals send to payers. It is machine-readable data, not a printable form."
                    />
                    {adjudicated && (
                        <EdiLink
                            claimId={claim.id}
                            kind="835"
                            label="Payment 835"
                            title="EDI 835 remittance advice"
                            detail="The payer's payment explanation as a raw ANSI X12 file: what was allowed, paid and left to the patient."
                        />
                    )}
                    {(claim.status === 'DENIED' || claim.status === 'PARTIALLY_PAID') && (
                        <button
                            onClick={onAppeal}
                            className="rounded-lg border border-amber-500/40 px-3 py-1.5 text-xs font-semibold text-amber-300 transition-colors hover:bg-amber-500/10"
                        >
                            Appeal
                        </button>
                    )}
                </div>
            </div>
        </motion.li>
    );
}
