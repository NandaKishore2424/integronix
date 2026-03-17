'use client';

import { CptCode } from '@/types/coding';
import { formatCurrency } from '@/lib/api';
import { ClipboardCheck, Activity } from 'lucide-react';

interface Props {
    codes: CptCode[];
}

export default function CptCodeList({ codes }: Props) {
    if (!codes || codes.length === 0) {
        return (
            <div className="glass-card p-6 flex flex-col items-center justify-center min-h-[200px] text-slate-500">
                <Activity className="w-8 h-8 mb-2 opacity-20" />
                <p className="text-sm font-mono">No procedural codes extracted</p>
                <span className="text-xs text-slate-400 max-w-sm mt-2 text-center">No CPT/HCPCS procedures were extracted for this case. This could mean it was an &quot;Evaluation and Management&quot; only visit.</span>
            </div>
        );
    }

    return (
        <div className="glass-card flex flex-col h-full border-t-2 border-t-indigo-500/50">
            <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <ClipboardCheck className="w-4 h-4 text-indigo-400" />
                    <h3 className="font-semibold text-sm tracking-tight text-white uppercase italic">
                        Procedural Billing (CPT/HCPCS)
                    </h3>
                </div>
                <span className="mono-label text-[10px] bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded-full border border-indigo-500/30">
                    CMS 2024 MPFS
                </span>
            </div>
            
            <div className="flex-1 overflow-y-auto max-h-[400px]">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="border-b border-white/5 bg-white/[0.02]">
                            <th className="px-6 py-3 mono-label text-[10px] w-24 text-slate-400">Code</th>
                            <th className="px-4 py-3 mono-label text-[10px] text-slate-400">Description</th>
                            <th className="px-6 py-3 mono-label text-[10px] text-right text-slate-400">Charge</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.05]">
                        {codes.map((c, idx) => (
                            <tr key={`${c.code}-${idx}`} className="group hover:bg-white/[0.03] transition-colors">
                                <td className="px-6 py-4 font-mono text-sm text-indigo-300 font-bold align-top">
                                    {c.code}
                                </td>
                                <td className="px-4 py-4 align-top">
                                    <div className="flex flex-col gap-1">
                                        <p className="text-sm text-slate-200 leading-tight">
                                            {c.description}
                                        </p>
                                        <div className="flex items-center gap-2">
                                            <span className="text-[10px] font-mono text-slate-500 italic bg-white/5 px-1.5 py-0.5 rounded">
                                                &quot;{c.original_text}&quot;
                                            </span>
                                            {c.confidence > 0.8 ? (
                                                <span className="text-[10px] font-mono text-success opacity-80 uppercase tracking-tighter">Matched</span>
                                            ) : (
                                                <span className="text-[10px] font-mono text-warning opacity-80 uppercase tracking-tighter text-[9px]">Check Text</span>
                                            )}
                                        </div>
                                    </div>
                                </td>
                                <td className="px-6 py-4 text-right align-top">
                                    <div className="flex flex-col items-end">
                                        <span className="text-sm font-mono font-bold text-white">
                                            {formatCurrency(c.gross_charge)}
                                        </span>
                                        <span className="text-[9px] font-mono text-slate-500">
                                            Ref: {formatCurrency(c.base_price)} x {c.multiplier}
                                        </span>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            
            <div className="p-4 bg-indigo-500/5 mt-auto">
                <p className="text-[10px] text-slate-500 font-mono leading-relaxed">
                    Charges summarized based on Hospital-Specific Chargemaster Multiplier. 
                    Calculated using semantic matching against 
                    standardized CMS healthcare common procedure coding system.
                </p>
            </div>
        </div>
    );
}
