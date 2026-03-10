'use client';

import { IcdCandidate } from '@/types/coding';
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { BarChart2 } from 'lucide-react';

interface Props { candidates: IcdCandidate[] }

const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
        <div className="glass-card px-3 py-2.5 text-xs max-w-[220px]">
            <p className="font-bold font-mono text-white mb-1">{d.code}</p>
            <p className="text-slate-300 mb-1.5 leading-snug">{d.description}</p>
            <div className="flex flex-col gap-0.5">
                <span className="text-slate-400">Score: <strong className="text-white">{(d.final_score * 100).toFixed(0)}%</strong></span>
                <span className="text-slate-400">Confidence: <strong className="text-white">{(d.confidence * 100).toFixed(0)}%</strong></span>
                {d.is_mcc && <span className="text-danger-light font-semibold">MCC</span>}
                {d.is_cc && !d.is_mcc && <span className="text-warning font-semibold">CC</span>}
            </div>
        </div>
    );
};

export default function CandidateChart({ candidates }: Props) {
    if (!candidates || candidates.length === 0) {
        return (
            <div className="glass-card p-6 flex items-center justify-center text-slate-500 text-sm">
                No candidate data available.
            </div>
        );
    }

    const data = [...candidates]
        .sort((a, b) => b.final_score - a.final_score)
        .slice(0, 6);

    // maxScore removed — Recharts XAxis domain={[0, 1]} handles scaling


    return (
        <div className="glass-card p-6 flex flex-col gap-4">
            <div className="section-header">
                <BarChart2 className="w-3 h-3" />
                Candidate Score Breakdown
            </div>

            <div style={{ height: 220 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data} layout="vertical" margin={{ left: 0, right: 20, top: 0, bottom: 0 }}>
                        <XAxis
                            type="number" domain={[0, 1]} hide
                        />
                        <YAxis
                            type="category"
                            dataKey="code"
                            width={60}
                            tick={{ fill: '#94a3b8', fontSize: 11, fontFamily: 'JetBrains Mono, monospace', fontWeight: 600 }}
                            axisLine={false}
                            tickLine={false}
                        />
                        <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                        <Bar dataKey="final_score" radius={[0, 4, 4, 0]} maxBarSize={28}>
                            {data.map((entry, idx) => (
                                <Cell
                                    key={entry.code}
                                    fill={
                                        idx === 0
                                            ? '#6366f1'
                                            : entry.final_score >= 0.6
                                                ? '#4f46e5'
                                                : entry.final_score >= 0.4
                                                    ? '#3b4fd0'
                                                    : '#1e2a6b'
                                    }
                                    opacity={idx === 0 ? 1 : 0.7 - idx * 0.08}
                                />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>

            {/* Legend */}
            <div className="flex flex-wrap gap-3 text-xs text-slate-500 pt-1 border-t border-white/[0.06]">
                <span className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-sm bg-accent inline-block" />
                    Selected (highest score)
                </span>
                <span className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-sm bg-[#1e2a6b] inline-block" />
                    Other candidates
                </span>
            </div>
        </div>
    );
}
