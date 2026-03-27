'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
    BarChart3, Shield, AlertTriangle, TrendingUp,
    FileText, ScanText, ChevronLeft, ChevronRight,
    Filter, RotateCcw, ExternalLink, Download
} from 'lucide-react';
import { fetchCases, fetchCaseStats, formatCurrency, formatConfidence } from '@/lib/api';
import { CaseSummary, CaseStatsResponse, CasesFilters } from '@/types/cases';

// ── Helpers ──────────────────────────────────────────────────────────────────

function riskStyle(label: string) {
    if (label === 'HIGH')   return { dot: 'bg-red-500',    text: 'text-red-400',    badge: 'bg-red-500/10 border-red-500/25 text-red-400' };
    if (label === 'MEDIUM') return { dot: 'bg-amber-400',  text: 'text-amber-400',  badge: 'bg-amber-400/10 border-amber-400/25 text-amber-400' };
    return                         { dot: 'bg-emerald-400', text: 'text-emerald-400', badge: 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400' };
}

function discrepancyLabel(d: string | null) {
    const map: Record<string, string> = {
        EXACT_MATCH:              '✓ Match',
        NO_COMPARISON:            '— No compare',
        SPECIFICITY_IMPROVEMENT:  '↑ Specificity',
        CODE_DIVERGENCE:          '⚠ Diverged',
        OVERCODING:               '⬆ Overcode',
        UNSUPPORTED_CODE:         '✗ Unsupported',
    };
    return d ? (map[d] ?? d) : '—';
}

function SourceBadge({ source, ocr }: { source: string | null; ocr: boolean | null }) {
    if (source === 'pdf_upload') {
        return ocr
            ? <span className="inline-flex items-center gap-1 text-[10px] font-mono text-amber-400 bg-amber-400/10 border border-amber-400/25 rounded px-1.5 py-0.5"><ScanText className="w-2.5 h-2.5" />OCR PDF</span>
            : <span className="inline-flex items-center gap-1 text-[10px] font-mono text-slate-400 bg-white/[0.04] border border-white/[0.08] rounded px-1.5 py-0.5"><FileText className="w-2.5 h-2.5" />PDF</span>;
    }
    return <span className="text-[10px] font-mono text-slate-500">Text</span>;
}

// ── Stat Card ─────────────────────────────────────────────────────────────────

function StatCard({ icon: Icon, value, label, color }: { icon: any; value: string; label: string; color: string }) {
    return (
        <div className="glass-card px-5 py-4 flex items-center gap-4">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
                <Icon className="w-5 h-5" />
            </div>
            <div>
                <p className="text-xl font-extrabold text-white leading-none">{value}</p>
                <p className="text-xs text-slate-500 mt-0.5">{label}</p>
            </div>
        </div>
    );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function CasesPage() {
    const router = useRouter();

    const [cases, setCases]     = useState<CaseSummary[]>([]);
    const [stats, setStats]     = useState<CaseStatsResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError]     = useState<string | null>(null);

    const [total, setTotal]     = useState(0);
    const [page, setPage]       = useState(1);
    const [totalPages, setTotalPages] = useState(1);

    const [filters, setFilters] = useState<CasesFilters>({});

    const loadData = useCallback(async (f: CasesFilters, p: number) => {
        setLoading(true);
        setError(null);
        try {
            const [listRes, statsRes] = await Promise.all([
                fetchCases({ ...f, page: p }),
                fetchCaseStats(),
            ]);
            setCases(listRes.cases);
            setTotal(listRes.total);
            setTotalPages(listRes.total_pages);
            setStats(statsRes);
        } catch (e: any) {
            setError(e.message ?? 'Failed to load cases.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { loadData(filters, page); }, [filters, page, loadData]);

    function applyFilter(key: keyof CasesFilters, value: string) {
        const next = { ...filters, [key]: value || undefined };
        setPage(1);
        setFilters(next);
    }

    function resetFilters() { setFilters({}); setPage(1); }

    function exportCsv() {
        const header = 'Date,AI Code,Human Code,Discrepancy,Revenue Delta,Risk,Source\n';
        const rows = cases.map(c => [
            new Date(c.created_at).toLocaleDateString(),
            c.ai_icd_code ?? '',
            c.human_icd_code ?? '',
            c.discrepancy_type ?? '',
            c.financial_delta ?? 0,
            c.risk_label,
            c.document_source ?? '',
        ].join(',')).join('\n');
        const blob = new Blob([header + rows], { type: 'text/csv' });
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        a.href     = url;
        a.download = `integronix_cases_${new Date().toISOString().slice(0,10)}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }

    const hasFilters = Object.keys(filters).some(k => !!filters[k as keyof CasesFilters]);

    return (
        <div className="min-h-screen flex flex-col">

            {/* Header strip */}
            <div className="border-b border-white/[0.06] px-6 py-3 flex items-center gap-4">
                <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
                    <BarChart3 className="w-3.5 h-3.5" />
                    <span>Case History</span>
                </div>
                <div className="ml-auto flex items-center gap-2">
                    {total > 0 && (
                        <button
                            onClick={exportCsv}
                            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white border border-white/10 hover:border-white/20 px-3 py-1.5 rounded-lg transition-colors"
                        >
                            <Download className="w-3 h-3" />
                            Export CSV
                        </button>
                    )}
                </div>
            </div>

            {/* Summary cards */}
            <div className="px-6 pt-6 pb-4">
                <div className="max-w-7xl mx-auto">
                    <div className="mb-5">
                        <h1 className="text-2xl font-extrabold text-white">Case History</h1>
                        <p className="text-sm text-slate-400 mt-1">All coding sessions analysed by the AI pipeline — click any row to open the full report.</p>
                    </div>

                    {stats ? (
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
                            <StatCard icon={BarChart3}    value={String(stats.total_cases)}                           label="Total Cases"           color="bg-amber-500/15 text-amber-400" />
                            <StatCard icon={TrendingUp}   value={stats.total_revenue_recovered > 0 ? formatCurrency(stats.total_revenue_recovered) : '—'} label="Revenue Recovered" color="bg-emerald-500/15 text-emerald-400" />
                            <StatCard icon={AlertTriangle} value={String(stats.high_risk_count)}                      label="HIGH Risk Flagged"     color="bg-red-500/15 text-red-400" />
                            <StatCard icon={Shield}        value={`${stats.accuracy_rate}%`}                          label="Accuracy Rate"         color="bg-violet-500/15 text-orange-400" />
                        </div>
                    ) : (
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
                            {[0,1,2,3].map(i => (
                                <div key={i} className="glass-card px-5 py-4 h-[72px] animate-pulse bg-white/[0.02]" />
                            ))}
                        </div>
                    )}

                    {/* Filter bar */}
                    <div className="flex flex-wrap items-center gap-2 mb-4">
                        <Filter className="w-3.5 h-3.5 text-slate-500 shrink-0" />

                        {/* Risk filter */}
                        <select
                            className="text-xs bg-white/[0.04] border border-white/[0.08] text-slate-300 rounded-lg px-3 py-1.5 focus:outline-none focus:border-amber-500/50"
                            value={filters.risk_label ?? ''}
                            onChange={e => applyFilter('risk_label', e.target.value)}
                        >
                            <option value="">All Risk Levels</option>
                            <option value="HIGH">HIGH</option>
                            <option value="MEDIUM">MEDIUM</option>
                            <option value="LOW">LOW</option>
                        </select>

                        {/* Source filter */}
                        <select
                            className="text-xs bg-white/[0.04] border border-white/[0.08] text-slate-300 rounded-lg px-3 py-1.5 focus:outline-none focus:border-amber-500/50"
                            value={filters.document_source ?? ''}
                            onChange={e => applyFilter('document_source', e.target.value)}
                        >
                            <option value="">All Sources</option>
                            <option value="pdf_upload">PDF Upload</option>
                            <option value="text_input">Text Input</option>
                        </select>

                        {hasFilters && (
                            <button
                                onClick={resetFilters}
                                className="flex items-center gap-1 text-xs text-slate-500 hover:text-white transition-colors px-2 py-1.5"
                            >
                                <RotateCcw className="w-3 h-3" /> Reset
                            </button>
                        )}

                        <span className="ml-auto text-xs text-slate-500">
                            {loading ? 'Loading…' : `${total} case${total !== 1 ? 's' : ''}`}
                        </span>
                    </div>

                    {/* Table */}
                    <div className="glass-card overflow-hidden">
                        {error ? (
                            <div className="p-8 text-center text-sm text-red-400">{error}</div>
                        ) : loading ? (
                            <div className="divide-y divide-white/[0.04]">
                                {[...Array(5)].map((_, i) => (
                                    <div key={i} className="px-5 py-4 animate-pulse flex gap-4">
                                        <div className="h-4 bg-white/[0.04] rounded w-24 shrink-0" />
                                        <div className="h-4 bg-white/[0.04] rounded w-16 shrink-0" />
                                        <div className="h-4 bg-white/[0.04] rounded flex-1" />
                                        <div className="h-4 bg-white/[0.04] rounded w-20 shrink-0" />
                                        <div className="h-4 bg-white/[0.04] rounded w-16 shrink-0" />
                                    </div>
                                ))}
                            </div>
                        ) : cases.length === 0 ? (
                            <div className="p-12 text-center">
                                <BarChart3 className="w-8 h-8 text-slate-600 mx-auto mb-3" />
                                <p className="text-sm font-semibold text-slate-400">No cases yet</p>
                                <p className="text-xs text-slate-600 mt-1">
                                    {hasFilters ? 'No cases match your current filters.' : 'Run an analysis from the Analyse page to see results here.'}
                                </p>
                            </div>
                        ) : (
                            <>
                                {/* Table header */}
                                <div className="grid grid-cols-[1fr_90px_90px_120px_100px_90px_36px] gap-3 px-5 py-2 border-b border-white/[0.06] bg-white/[0.02]">
                                    {['Date & Source', 'AI Code', 'Human Code', 'Discrepancy', 'Revenue Δ', 'Risk', ''].map((h, i) => (
                                        <span key={i} className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{h}</span>
                                    ))}
                                </div>

                                {/* Rows */}
                                <div className="divide-y divide-white/[0.04]">
                                    {cases.map(c => {
                                        const rs    = riskStyle(c.risk_label);
                                        const delta = c.financial_delta ?? 0;
                                        const date  = new Date(c.created_at);
                                        return (
                                            <div
                                                key={c.result_id}
                                                onClick={() => router.push(`/hospital/coder/history/${c.session_id}`)}
                                                className="grid grid-cols-[1fr_90px_90px_120px_100px_90px_36px] gap-3 px-5 py-3.5 cursor-pointer hover:bg-white/[0.03] transition-colors items-center group"
                                            >
                                                {/* Date + Source */}
                                                <div className="min-w-0">
                                                    <p className="text-xs font-semibold text-slate-200">
                                                        {date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' })}
                                                        <span className="ml-1.5 text-[10px] text-slate-600">
                                                            {date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })}
                                                        </span>
                                                    </p>
                                                    <div className="mt-0.5">
                                                        <SourceBadge source={c.document_source} ocr={c.ocr_used} />
                                                    </div>
                                                    {c.text_snippet && (
                                                        <p className="text-[10px] text-slate-600 truncate mt-0.5 max-w-[260px]">{c.text_snippet}</p>
                                                    )}
                                                </div>

                                                {/* AI Code */}
                                                <span className="text-xs font-mono font-bold text-amber-300">
                                                    {c.ai_icd_code ?? '—'}
                                                </span>

                                                {/* Human Code */}
                                                <span className="text-xs font-mono text-slate-400">
                                                    {c.human_icd_code ?? <span className="text-slate-600 text-[10px]">None</span>}
                                                </span>

                                                {/* Discrepancy */}
                                                <span className={`text-[11px] font-semibold ${
                                                    c.discrepancy_type === 'EXACT_MATCH' ? 'text-emerald-400' :
                                                    c.discrepancy_type === 'NO_COMPARISON' ? 'text-slate-500' :
                                                    'text-amber-400'
                                                }`}>
                                                    {discrepancyLabel(c.discrepancy_type)}
                                                </span>

                                                {/* Revenue delta */}
                                                <span className={`text-xs font-bold ${
                                                    delta > 0 ? 'text-emerald-400' :
                                                    delta < 0 ? 'text-red-400' :
                                                    'text-slate-500'
                                                }`}>
                                                    {delta !== 0 ? formatCurrency(delta) : '—'}
                                                </span>

                                                {/* Risk badge */}
                                                <div className="flex items-center">
                                                    <span className={`inline-flex items-center gap-1.5 text-[11px] font-bold border rounded-full px-2.5 py-0.5 ${rs.badge}`}>
                                                        <span className={`w-1.5 h-1.5 rounded-full ${rs.dot}`} />
                                                        {c.risk_label}
                                                    </span>
                                                </div>

                                                {/* Open icon */}
                                                <ExternalLink className="w-3.5 h-3.5 text-slate-600 group-hover:text-slate-400 transition-colors" />
                                            </div>
                                        );
                                    })}
                                </div>
                            </>
                        )}
                    </div>

                    {/* Pagination */}
                    {totalPages > 1 && (
                        <div className="flex items-center justify-between mt-4">
                            <span className="text-xs text-slate-500">
                                Page {page} of {totalPages} · {total} cases
                            </span>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => setPage(p => Math.max(1, p - 1))}
                                    disabled={page <= 1 || loading}
                                    className="p-2 rounded-lg border border-white/10 hover:border-white/20 text-slate-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                                >
                                    <ChevronLeft className="w-4 h-4" />
                                </button>
                                <button
                                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                                    disabled={page >= totalPages || loading}
                                    className="p-2 rounded-lg border border-white/10 hover:border-white/20 text-slate-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                                >
                                    <ChevronRight className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                    )}

                </div>
            </div>

        </div>
    );
}
