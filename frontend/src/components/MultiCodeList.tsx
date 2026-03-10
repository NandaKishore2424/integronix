'use client';

import { IcdCode } from '@/types/coding';
import { Award, Star, Plus } from 'lucide-react';

interface Props { codes: IcdCode[] }

const ROLE_CONFIG = {
    primary: { label: 'Primary Diagnosis', icon: Award, color: 'text-accent-light', bg: 'border-accent/25 bg-accent/10' },
    secondary: { label: 'Secondary', icon: Star, color: 'text-warning', bg: 'border-warning/20 bg-warning/8' },
    additional: { label: 'Additional', icon: Plus, color: 'text-slate-400', bg: 'border-white/10 bg-white/[0.03]' },
};

export default function MultiCodeList({ codes }: Props) {
    if (!codes || codes.length === 0) {
        return (
            <div className="glass-card p-6 flex items-center justify-center text-slate-500 text-sm">
                No codes returned for this case.
            </div>
        );
    }

    return (
        <div className="glass-card p-6 flex flex-col gap-4">
            <div className="section-header">
                <Award className="w-3 h-3" />
                ICD-10-CM Code Recommendations
            </div>

            <div className="flex flex-col gap-3">
                {codes.map((c) => {
                    const cfg = ROLE_CONFIG[c.role] ?? ROLE_CONFIG.additional;
                    const Icon = cfg.icon;
                    const pct = Math.round(c.final_score * 100);

                    return (
                        <div key={`${c.code}-${c.role}`} className={`rounded-xl border p-4 transition-all ${cfg.bg}`}>
                            <div className="flex items-start justify-between gap-3">
                                <div className="flex items-start gap-3">

                                    {/* Role icon */}
                                    <div className="mt-0.5">
                                        <Icon className={`w-4 h-4 ${cfg.color}`} />
                                    </div>

                                    <div className="flex-1">
                                        {/* Code + role label */}
                                        <div className="flex items-center gap-2 flex-wrap mb-1">
                                            <span className="text-base font-bold font-mono text-white">{c.code}</span>
                                            <span className={`text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded ${cfg.color} bg-black/20`}>
                                                {cfg.label}
                                            </span>
                                            {c.is_mcc && (
                                                <span className="text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded bg-danger/15 text-danger-light border border-danger/25">
                                                    High Severity
                                                </span>
                                            )}
                                            {c.is_cc && !c.is_mcc && (
                                                <span className="text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded bg-warning/15 text-warning-light border border-warning/25">
                                                    Complication
                                                </span>
                                            )}
                                        </div>

                                        {/* Description */}
                                        <p className="text-sm text-slate-300 leading-snug mb-2">{c.description}</p>

                                        {/* Rationale */}
                                        <p className="text-xs text-slate-500 italic">{c.rationale}</p>
                                    </div>
                                </div>

                                {/* Score + reimbursement */}
                                <div className="text-right shrink-0">
                                    <p className="text-lg font-bold text-white">{pct}%</p>
                                    <p className="text-xs text-slate-500">${c.base_reimbursement.toLocaleString()}</p>
                                </div>
                            </div>

                            {/* Score bar */}
                            <div className="mt-3 conf-bar-track">
                                <div
                                    className="conf-bar-fill"
                                    style={{
                                        width: `${pct}%`,
                                        background: c.role === 'primary'
                                            ? 'linear-gradient(90deg, #6366f1, #818cf8)'
                                            : c.role === 'secondary'
                                                ? 'linear-gradient(90deg, #f59e0b, #fcd34d)'
                                                : 'linear-gradient(90deg, #64748b, #94a3b8)',
                                    }}
                                />
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* FIX FE-BUG-009: Show primary code reimbursement only.
                Summing all codes is clinically misleading — DRG reimbursement
                is determined by the principal diagnosis grouping, not additive per code. */}
            <div className="border-t border-white/[0.06] pt-3 flex justify-between items-center gap-3 flex-wrap">
                <div>
                    <span className="text-xs text-slate-500">Estimated Reimbursement</span>
                    <span className="text-xs text-slate-600 ml-1">(primary DRG rate)</span>
                </div>
                <div className="text-right">
                    <span className="text-sm font-bold text-success">
                        ${(codes.find(c => c.role === 'primary')?.base_reimbursement ?? 0).toLocaleString()}
                    </span>
                    {codes.length > 1 && (
                        <p className="text-[10px] text-slate-600 mt-0.5">
                            +{codes.length - 1} additional code{codes.length > 2 ? 's' : ''} affect DRG weight
                        </p>
                    )}
                </div>
            </div>
        </div>
    );
}
