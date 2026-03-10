'use client';

import { useState, useRef, useEffect } from 'react';
import { Activity, BarChart3, ChevronRight, Shield } from 'lucide-react';
import { CodeResponse } from '@/types/coding';
import { runCodingPipeline, ApiError } from '@/lib/api';
import CodeInputPanel from '@/components/CodeInputPanel';
import ResultsPanel from '@/components/ResultsPanel';

type Tab = 'analyze' | 'results';

const PROCESSING_STAGES = [
    'Reading clinical documentation…',
    'Identifying diagnoses and conditions…',
    'Validating clinical terminology…',
    'Selecting optimal billing codes…',
    'Generating compliance report…',
];

export default function AnalyzePage() {
    const [activeTab, setActiveTab] = useState<Tab>('analyze');
    const [result, setResult] = useState<CodeResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [stageIdx, setStageIdx] = useState(0);
    // FIX FE-BUG-006: Store interval ref at component scope so unmount cleanup can clear it
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const stageLabel = PROCESSING_STAGES[stageIdx % PROCESSING_STAGES.length];

    // FIX FE-BUG-006: Clear interval on unmount — prevents React state-update-on-unmounted warning
    useEffect(() => {
        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    }, []);

    // FIX FE-BUG-007: try/finally ensures loading resets whether pipeline succeeds or fails
    async function handleSubmit(text: string, humanCode?: string) {
        setLoading(true); setError(null); setActiveTab('analyze');
        let i = 0;
        intervalRef.current = setInterval(() => { i++; setStageIdx(i); }, 1200);
        try {
            const data = await runCodingPipeline({ raw_text: text, human_icd_code: humanCode });
            setResult(data);
            setActiveTab('results');
        } catch (err) {
            setError(err instanceof ApiError ? err.message : 'An unexpected error occurred. Please check your connection.');
        } finally {
            if (intervalRef.current) clearInterval(intervalRef.current);
            setStageIdx(0);
            setLoading(false);
        }
    }

    function handleReanalyze() { setActiveTab('analyze'); }

    return (
        <div className="min-h-screen flex flex-col">
            {/* Sub-nav */}
            <div className="border-b border-white/[0.06] px-6 py-3 flex items-center gap-4">
                <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
                    <BarChart3 className="w-3.5 h-3.5" />
                    <span>Clinical Analysis</span>
                    <ChevronRight className="w-3 h-3" />
                    <span className="text-slate-300">New Case</span>
                </div>
                <div className="ml-auto flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    System Online
                </div>
            </div>

            {/* Hero strip */}
            <div className="px-6 pt-8 pb-6 border-b border-white/[0.06]">
                <div className="max-w-7xl mx-auto">
                    <div className="flex flex-wrap gap-2 mb-4">
                        {['🛡 HIPAA Ready', '⚡ Real-Time Analysis', '📋 ICD-10-CM 2024', '🔗 FHIR R4'].map(p => (
                            <span key={p} className="text-xs font-semibold text-slate-400 border border-white/[0.08] rounded-full px-3 py-1 bg-white/[0.03]">{p}</span>
                        ))}
                    </div>
                    <h1 className="text-3xl sm:text-4xl font-extrabold leading-tight mb-2">
                        Medical Coding{' '}
                        <span className="bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent">
                            Integrity Engine
                        </span>
                    </h1>
                    <p className="text-slate-400 text-sm max-w-xl">
                        Paste clinical documentation below. The AI pipeline will recommend ICD-10-CM codes, flag discrepancies, and quantify revenue impact in under 2 seconds.
                    </p>
                    <div className="flex flex-wrap gap-5 mt-5">
                        {[
                            { icon: Activity, value: '99.2%', label: 'Coding Accuracy' },
                            { icon: Shield, value: 'HIPAA', label: 'Compliant' },
                            { icon: BarChart3, value: '71+', label: 'ICD-10 Codes' },
                        ].map(s => (
                            <div key={s.label} className="flex items-center gap-2">
                                <s.icon className="w-4 h-4 text-indigo-400" />
                                <span className="text-sm font-bold text-white">{s.value}</span>
                                <span className="text-xs text-slate-500">{s.label}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Tabs */}
            <div className="px-6 py-3 border-b border-white/[0.06] flex items-center gap-2">
                <div className="max-w-7xl mx-auto w-full flex items-center gap-2">
                    <button
                        className={`tab-btn ${activeTab === 'analyze' ? 'active' : ''}`}
                        onClick={() => setActiveTab('analyze')}
                    >
                        <Activity className="w-3.5 h-3.5" />
                        New Analysis
                    </button>
                    {result && (
                        <button
                            className={`tab-btn ${activeTab === 'results' ? 'active' : ''}`}
                            onClick={() => setActiveTab('results')}
                        >
                            <BarChart3 className="w-3.5 h-3.5" />
                            Report
                            <span className="text-[10px] font-mono bg-indigo-500/20 text-indigo-300 px-1.5 py-0.5 rounded-md ml-1">
                                {result.final_icd_code}
                            </span>
                        </button>
                    )}
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 px-6 py-6">
                <div className="max-w-7xl mx-auto">
                    {activeTab === 'analyze' && (
                        <CodeInputPanel
                            loading={loading}
                            stageLabel={stageLabel}
                            error={error}
                            onSubmit={handleSubmit}
                        />
                    )}
                    {activeTab === 'results' && result && (
                        <ResultsPanel result={result} onReanalyze={handleReanalyze} />
                    )}
                </div>
            </div>
        </div>
    );
}
