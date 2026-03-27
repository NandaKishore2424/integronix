'use client';

import { RiskLabel } from '@/types/coding';
import { ShieldCheck, ShieldAlert, Shield } from 'lucide-react';

interface Props {
    score: number;
    label: RiskLabel;
    confidence: number;
}

const RISK_CFG = {
    LOW: { color: '#22c55e', trackColor: 'rgba(34,197,94,0.15)', border: 'border-success/25', bg: 'bg-success/10', text: 'text-success', icon: ShieldCheck, tip: 'Coding quality is high. Low probability of audit trigger.' },
    MEDIUM: { color: '#f59e0b', trackColor: 'rgba(245,158,11,0.15)', border: 'border-warning/25', bg: 'bg-warning/10', text: 'text-warning', icon: ShieldAlert, tip: 'Moderate audit risk. Review discrepancy details.' },
    HIGH: { color: '#ef4444', trackColor: 'rgba(239,68,68,0.15)', border: 'border-danger/25', bg: 'bg-danger/10', text: 'text-danger', icon: Shield, tip: 'High audit risk. Immediate review recommended.' },
    UNKNOWN: { color: '#64748b', trackColor: 'rgba(100,116,139,0.15)', border: 'border-slate-700', bg: 'bg-slate-800/50', text: 'text-slate-400', icon: Shield, tip: 'Risk level could not be determined.' },
};

export default function RiskMeter({ score, label, confidence }: Props) {
    const cfg = RISK_CFG[label] ?? RISK_CFG.UNKNOWN;
    const Icon = cfg.icon;
    const pct = Math.round(score * 100);
    const confPct = Math.round(confidence * 100);
    const radius = 54;
    const circumf = 2 * Math.PI * radius;
    const dash = (pct / 100) * circumf;

    return (
        <div className={`glass-card p-6 h-full flex flex-col gap-4 items-center border ${cfg.border} ${cfg.bg}`}>

            <div className="section-header w-full">
                <Icon className="w-3.5 h-3.5" />
                Risk Assessment
            </div>

            {/* SVG gauge */}
            <div className="relative w-32 h-32">
                <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
                    {/* Track */}
                    <circle cx="60" cy="60" r={radius} fill="none" strokeWidth="10"
                        stroke={cfg.trackColor} />
                    {/* Fill */}
                    <circle cx="60" cy="60" r={radius} fill="none" strokeWidth="10"
                        stroke={cfg.color}
                        strokeDasharray={`${dash} ${circumf - dash}`}
                        strokeLinecap="round"
                        style={{ transition: 'stroke-dasharray 0.8s ease-out', filter: `drop-shadow(0 0 8px ${cfg.color}60)` }}
                    />
                </svg>
                {/* Center label */}
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-2xl font-extrabold text-white">{pct}%</span>
                    <span className={`text-xs font-bold uppercase tracking-widest ${cfg.text}`}>{label}</span>
                </div>
            </div>

            {/* Tip */}
            <p className="text-xs text-slate-400 text-center leading-relaxed">{cfg.tip}</p>

            {/* Stats row */}
            <div className="w-full grid grid-cols-2 gap-3 pt-2 border-t border-white/[0.06]">
                <div className="flex flex-col items-center gap-1 group relative">
                    <span className="mono-label cursor-help border-b border-dashed border-slate-600">Risk Score</span>
                    <span className={`text-lg font-bold ${cfg.text}`}>{pct}%</span>
                    <div className="invisible group-hover:visible opacity-0 group-hover:opacity-100 transition-opacity absolute bottom-full mb-2 w-48 p-2 bg-slate-800 text-[10px] leading-snug text-slate-300 rounded shadow-lg z-10 border border-slate-700 text-center pointer-events-none">
                        Probability of payer denial or audit based on historical data.
                    </div>
                </div>
                <div className="flex flex-col items-center gap-1 group relative">
                    <span className="mono-label cursor-help border-b border-dashed border-slate-600">AI Confidence</span>
                    <span className="text-lg font-bold text-white">{confPct}%</span>
                    <div className="invisible group-hover:visible opacity-0 group-hover:opacity-100 transition-opacity absolute bottom-full mb-2 w-48 p-2 bg-slate-800 text-[10px] leading-snug text-slate-300 rounded shadow-lg z-10 border border-slate-700 text-center pointer-events-none">
                        AI certainty of clinical to ICD-10 crosswalk match.
                    </div>
                </div>
            </div>

        </div>
    );
}
