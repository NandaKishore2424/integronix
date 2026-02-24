'use client';

import { Discrepancy, DrgFlag } from '@/types/coding';
import { formatCurrency } from '@/lib/api';
import DrgBadge from './DrgBadge';
import { ArrowLeftRight, TrendingUp, TrendingDown, CheckCircle2, AlertOctagon } from 'lucide-react';

interface Props {
    discrepancy: Discrepancy;
    financialDelta: number;
    drgFlag: DrgFlag;
}

const DISCREPANCY_CFG: Record<string, { label: string; color: string; bg: string; border: string; icon: typeof CheckCircle2 }> = {
    EXACT_MATCH: { label: 'Exact Match', color: 'text-success', bg: 'bg-success/10', border: 'border-success/25', icon: CheckCircle2 },
    SPECIFICITY_IMPROVEMENT: { label: 'Specificity Improvement', color: 'text-accent-light', bg: 'bg-accent/10', border: 'border-accent/25', icon: TrendingUp },
    OVERCODING: { label: 'Overcoding Detected', color: 'text-danger', bg: 'bg-danger/10', border: 'border-danger/25', icon: AlertOctagon },
    UNSUPPORTED_CODE: { label: 'Unsupported Code', color: 'text-warning', bg: 'bg-warning/10', border: 'border-warning/25', icon: AlertOctagon },
};

export default function AuditCard({ discrepancy: d, financialDelta: delta, drgFlag }: Props) {
    const cfg = DISCREPANCY_CFG[d.type] ?? DISCREPANCY_CFG['UNSUPPORTED_CODE'];
    const Icon = cfg.icon;

    return (
        <div className="glass-card p-6 flex flex-col gap-5">
            <div className="flex items-center justify-between flex-wrap gap-3">
                <div className="section-header mb-0">
                    <ArrowLeftRight className="w-3.5 h-3.5" />
                    Audit Comparison
                </div>
                <span className={`flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide px-3 py-1.5 rounded-lg border ${cfg.color} ${cfg.bg} ${cfg.border}`}>
                    <Icon className="w-3.5 h-3.5" />
                    {cfg.label}
                </span>
            </div>

            {/* Side by side */}
            <div className="grid grid-cols-2 gap-4">
                {/* AI */}
                <div className="rounded-xl border border-accent/20 bg-accent/[0.06] p-4">
                    <p className="mono-label mb-2">AI Code (Recommended)</p>
                    <p className="text-2xl font-extrabold font-mono text-white mb-1">{d.ai_code}</p>
                    <p className="text-sm text-slate-300 leading-snug">{d.ai_description}</p>
                    {d.ai_is_mcc && <span className="mt-2 inline-block text-[10px] font-bold px-2 py-0.5 rounded bg-danger/15 border border-danger/30 text-danger-light">MCC</span>}
                    {d.ai_is_cc && !d.ai_is_mcc && <span className="mt-2 inline-block text-[10px] font-bold px-2 py-0.5 rounded bg-warning/15 border border-warning/30 text-warning">CC</span>}
                </div>

                {/* Human */}
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4">
                    <p className="mono-label mb-2">Human Code (Submitted)</p>
                    <p className="text-2xl font-extrabold font-mono text-slate-300 mb-1">{d.human_code}</p>
                    <p className="text-sm text-slate-400 leading-snug">{d.human_description}</p>
                </div>
            </div>

            {/* Explanation */}
            <div className="rounded-xl bg-white/[0.03] border border-white/[0.06] p-4">
                <p className="text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Analysis</p>
                <p className="text-sm text-slate-200 leading-relaxed">{d.explanation}</p>
            </div>

            {/* Revenue delta */}
            {delta !== 0 && (
                <div className="flex items-center justify-between rounded-xl border px-5 py-4 bg-white/[0.02]"
                    style={{ borderColor: delta > 0 ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)' }}
                >
                    <div>
                        <p className="mono-label mb-1">Revenue Impact</p>
                        <p className="text-3xl font-extrabold" style={{ color: delta > 0 ? '#4ade80' : '#f87171' }}>
                            {formatCurrency(delta)}
                        </p>
                        <p className="text-xs text-slate-500 mt-0.5">
                            {delta > 0 ? 'Potential revenue recovery per claim' : 'Overcoding exposure per claim'}
                        </p>
                    </div>
                    {delta > 0
                        ? <TrendingUp className="w-10 h-10 text-success opacity-30" />
                        : <TrendingDown className="w-10 h-10 text-danger opacity-30" />}
                </div>
            )}

            {/* DRG badge */}
            {drgFlag && <DrgBadge flag={drgFlag} />}
        </div>
    );
}
