'use client';

import { FhirCondition } from '@/types/coding';
import { useState } from 'react';
import { ChevronDown, ChevronRight, Copy, Check, Activity } from 'lucide-react';

interface Props { fhir: FhirCondition }

export default function FhirPanel({ fhir }: Props) {
    const [open, setOpen] = useState(false);
    const [copied, setCopied] = useState(false);

    // FIX FE-BUG-005: async + await + fallback for Safari/mobile/HTTP clipboard failures
    async function copyJson() {
        const text = JSON.stringify(fhir, null, 2);
        try {
            await navigator.clipboard.writeText(text);
        } catch {
            // Fallback — execCommand is deprecated but universally supported
            const el = document.createElement('textarea');
            el.value = text;
            el.style.position = 'fixed';
            el.style.opacity = '0';
            document.body.appendChild(el);
            el.select();
            document.execCommand('copy');
            document.body.removeChild(el);
        }
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    }

    const codings = fhir.code?.coding ?? [];

    return (
        <div className="glass-card overflow-hidden">

            {/* Header (always visible) */}
            <button
                onClick={() => setOpen(o => !o)}
                className="w-full flex items-center justify-between px-6 py-4 hover:bg-white/[0.03] transition-colors"
            >
                <div className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
                        <Activity className="w-3 h-3 text-indigo-400" />
                    </div>
                    <div className="text-left">
                        <p className="text-sm font-semibold text-white">Interoperability Export</p>
                        <p className="text-xs text-slate-500">{codings.length} ICD-10 code{codings.length !== 1 ? 's' : ''} · Ready for EHR integration</p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <span className="text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded bg-indigo-500/15 border border-indigo-500/25 text-indigo-300">
                        HL7 FHIR R4
                    </span>
                    {open
                        ? <ChevronDown className="w-4 h-4 text-slate-500" />
                        : <ChevronRight className="w-4 h-4 text-slate-500" />}
                </div>
            </button>

            {/* Expanded content */}
            {open && (
                <div className="border-t border-white/[0.06] animate-fade-in">

                    {/* Coding summary table */}
                    <div className="px-6 py-4 border-b border-white/[0.06]">
                        <p className="mono-label mb-3">Encoded Diagnoses</p>
                        <div className="flex flex-col gap-2">
                            {codings.map((c, i) => (
                                <div key={c.code} className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.03] border border-white/[0.05]">
                                    <span className={`text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded mt-0.5 ${i === 0 ? 'bg-accent/20 text-accent-light border border-accent/30' : 'bg-white/[0.06] text-slate-400 border border-white/10'
                                        }`}>
                                        {i === 0 ? 'PRIMARY' : c.extension?.[0]?.valueString?.toUpperCase() ?? 'OTHER'}
                                    </span>
                                    <div>
                                        <p className="text-sm font-mono font-bold text-white">{c.code}</p>
                                        <p className="text-xs text-slate-400">{c.display}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Raw JSON */}
                    <div className="relative">
                        <button
                            onClick={copyJson}
                            className="absolute top-4 right-4 z-10 flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border border-white/10 bg-white/[0.06] text-slate-300 hover:text-white hover:border-white/20 transition-all"
                        >
                            {copied ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
                            {copied ? 'Copied!' : 'Copy JSON'}
                        </button>
                        <pre className="overflow-x-auto px-6 py-5 text-[11px] leading-relaxed font-mono text-slate-300 bg-black/20">
                            {JSON.stringify(fhir, null, 2)}
                        </pre>
                    </div>

                </div>
            )}
        </div>
    );
}
