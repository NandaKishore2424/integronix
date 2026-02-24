'use client';

import { useState } from 'react';
import { Send, Loader2, AlertCircle, FileText, Hash, Lightbulb } from 'lucide-react';

interface Props {
    onSubmit: (text: string, humanCode: string) => void;
    loading: boolean;
    stageLabel: string;
    error: string | null;
}

const SAMPLE_CASES = [
    {
        label: 'Diabetes + CKD',
        text: 'Patient has Type 2 diabetes mellitus with chronic kidney disease stage 3. eGFR is 42 mL/min. Blood pressure controlled with lisinopril.',
        code: 'E11.9',
    },
    {
        label: 'Low Back Pain',
        text: 'Patient reports chronic low back pain for 6 months, radiating to the left leg. Pain score 7/10. No prior surgery.',
        code: '',
    },
    {
        label: 'DM No Complications',
        text: 'Patient has diabetes. No complications documented. Blood glucose slightly elevated. No kidney disease noted.',
        code: '',
    },
];

export default function CodeInputPanel({ onSubmit, loading, stageLabel, error }: Props) {
    const [text, setText] = useState('');
    const [humanCode, setHumanCode] = useState('');

    function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        if (!text.trim() || text.trim().length < 20) return;
        onSubmit(text, humanCode);
    }

    function loadSample(s: typeof SAMPLE_CASES[0]) {
        setText(s.text);
        setHumanCode(s.code);
    }

    const charCount = text.trim().length;
    const canSubmit = charCount >= 20 && !loading;

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fade-in">

            {/* ── Main input ── */}
            <div className="lg:col-span-2 glass-card p-6">
                <form onSubmit={handleSubmit} className="flex flex-col gap-5 h-full">

                    {/* Clinical notes */}
                    <div>
                        <div className="flex items-center justify-between mb-2">
                            <label className="flex items-center gap-2 text-sm font-semibold text-slate-200">
                                <FileText className="w-4 h-4 text-accent-light" />
                                Clinical Documentation
                            </label>
                            <span className={`text-xs font-mono ${charCount >= 20 ? 'text-slate-500' : 'text-warning'}`}>
                                {charCount} chars {charCount < 20 ? `(need ${20 - charCount} more)` : ''}
                            </span>
                        </div>
                        <textarea
                            className="clinical-textarea"
                            rows={9}
                            placeholder={`Paste clinical notes, discharge summary, or SOAP note here…\n\nExample:\n"Patient has Type 2 diabetes mellitus with chronic kidney disease stage 3. eGFR is 42 mL/min."`}
                            value={text}
                            onChange={e => setText(e.target.value)}
                            disabled={loading}
                        />
                    </div>

                    {/* Human ICD code (optional) */}
                    <div>
                        <label className="flex items-center gap-2 text-sm font-semibold text-slate-200 mb-2">
                            <Hash className="w-4 h-4 text-slate-400" />
                            Human Coder ICD-10 Code
                            <span className="text-xs font-normal text-slate-500 ml-1">(optional — enables audit comparison)</span>
                        </label>
                        <input
                            type="text"
                            className="clinical-textarea font-mono uppercase"
                            style={{ height: '44px', resize: 'none' }}
                            placeholder="e.g. E11.9"
                            value={humanCode}
                            onChange={e => setHumanCode(e.target.value.toUpperCase())}
                            disabled={loading}
                            maxLength={10}
                        />
                    </div>

                    {/* Error */}
                    {error && (
                        <div className="flex items-start gap-3 rounded-xl border border-danger/25 bg-danger/10 px-4 py-3 text-sm text-danger-light animate-fade-in">
                            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                            <span>{error}</span>
                        </div>
                    )}

                    {/* Submit */}
                    <div className="flex items-center justify-between pt-1">
                        {loading ? (
                            <div className="flex items-center gap-3 text-sm text-slate-400 animate-fade-in">
                                <Loader2 className="w-4 h-4 animate-spin text-accent-light" />
                                <span className="text-accent-light font-medium">{stageLabel}</span>
                            </div>
                        ) : (
                            <span className="text-xs text-slate-600">
                                Pipeline: 8 nodes · LLaMA-3.3-70B · SNOMED-CT-2024
                            </span>
                        )}
                        <button type="submit" className="btn-primary flex items-center gap-2" disabled={!canSubmit}>
                            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                            {loading ? 'Analysing…' : 'Run Analysis'}
                        </button>
                    </div>
                </form>
            </div>

            {/* ── Sidebar: samples + tips ── */}
            <div className="flex flex-col gap-4">

                {/* Sample cases */}
                <div className="glass-card p-5">
                    <div className="section-header">
                        <Lightbulb className="w-3 h-3" />
                        Sample Cases
                    </div>
                    <div className="flex flex-col gap-2">
                        {SAMPLE_CASES.map(s => (
                            <button
                                key={s.label}
                                onClick={() => loadSample(s)}
                                disabled={loading}
                                className="text-left p-3 rounded-lg border border-white/[0.06] hover:border-accent/30 hover:bg-white/[0.04] transition-all duration-150 group"
                            >
                                <p className="text-sm font-semibold text-slate-200 group-hover:text-accent-light transition-colors">
                                    {s.label}
                                </p>
                                <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{s.text}</p>
                                {s.code && (
                                    <span className="mt-1.5 inline-block text-xs font-mono text-slate-400 bg-white/[0.04] px-2 py-0.5 rounded">
                                        Human: {s.code}
                                    </span>
                                )}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Pipeline info */}
                <div className="glass-card p-5">
                    <div className="section-header">Pipeline</div>
                    <ol className="flex flex-col gap-2">
                        {[
                            ['1', 'Clinical Extraction', 'LLaMA-3.3-70B via Groq'],
                            ['2', 'SNOMED Resolution', '2-word sliding window'],
                            ['3', 'ICD Mapping', 'SNOMED→ICD crosswalk'],
                            ['4', 'Embedding Fallback', 'pgvector cosine search'],
                            ['5', 'ICD Decision', '7-step deterministic'],
                            ['6', 'Audit Comparison', 'DRG-aware gap detection'],
                            ['7', 'Risk Scoring', 'MCC/CC weight analysis'],
                        ].map(([n, name, desc]) => (
                            <li key={n} className="flex items-start gap-2.5">
                                <span className="shrink-0 w-5 h-5 rounded-full bg-accent/15 border border-accent/30 flex items-center justify-center text-[10px] font-bold text-accent-light">
                                    {n}
                                </span>
                                <div>
                                    <p className="text-xs font-semibold text-slate-200">{name}</p>
                                    <p className="text-[11px] text-slate-500">{desc}</p>
                                </div>
                            </li>
                        ))}
                    </ol>
                </div>

            </div>
        </div>
    );
}
