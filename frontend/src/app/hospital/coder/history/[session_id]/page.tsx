'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Loader2, AlertCircle, BarChart3 } from 'lucide-react';
import { fetchCaseDetail, ApiError } from '@/lib/api';
import { CodeResponse } from '@/types/coding';
import ResultsPanel from '@/components/ResultsPanel';

export default function CaseDetailPage() {
    const { session_id } = useParams<{ session_id: string }>();
    const router         = useRouter();

    const [result, setResult]   = useState<CodeResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError]     = useState<string | null>(null);

    useEffect(() => {
        if (!session_id) return;
        setLoading(true);
        fetchCaseDetail(session_id)
            .then(setResult)
            .catch(e => setError(e instanceof ApiError ? e.message : 'Failed to load case.'))
            .finally(() => setLoading(false));
    }, [session_id]);

    return (
        <div className="min-h-screen flex flex-col">

            {/* Breadcrumb */}
            <div className="border-b border-white/[0.06] px-6 py-3 flex items-center gap-3">
                <button
                    onClick={() => router.back()}
                    className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors"
                >
                    <ArrowLeft className="w-3.5 h-3.5" />
                    Back to Cases
                </button>
                <span className="text-slate-700">·</span>
                <div className="flex items-center gap-2 text-xs text-slate-500">
                    <BarChart3 className="w-3.5 h-3.5" />
                    Case Detail
                    {result && (
                        <>
                            <span className="text-slate-700">·</span>
                            <span className="font-mono text-indigo-400">{result.final_icd_code}</span>
                        </>
                    )}
                </div>
            </div>

            <div className="flex-1 px-6 py-6">
                <div className="max-w-7xl mx-auto">

                    {loading && (
                        <div className="flex items-center gap-3 text-sm text-slate-400 py-12 justify-center">
                            <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
                            Loading case report…
                        </div>
                    )}

                    {error && (
                        <div className="flex items-start gap-3 glass-card p-5 border-red-500/20 bg-red-500/5 text-sm text-red-400 max-w-lg mx-auto mt-8">
                            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                            <div>
                                <p className="font-semibold">Failed to load case</p>
                                <p className="text-xs mt-1 text-red-400/70">{error}</p>
                            </div>
                        </div>
                    )}

                    {!loading && !error && result && (
                        <ResultsPanel result={result} onReanalyze={() => router.push('/hospital/coder/analyze')} />
                    )}

                </div>
            </div>

        </div>
    );
}
