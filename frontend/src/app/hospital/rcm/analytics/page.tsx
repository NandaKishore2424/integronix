'use client';

import { useState, useEffect } from 'react';
import {
    BarChart3, TrendingUp, Shield, AlertTriangle,
    FileText, Activity,
} from 'lucide-react';
import {
    ResponsiveContainer,
    AreaChart, Area,
    BarChart, Bar,
    PieChart, Pie, Cell,
    XAxis, YAxis, Tooltip, CartesianGrid,
    Legend,
} from 'recharts';
import {
    fetchAnalyticsOverview,
    fetchTopCodes,
    fetchDiscrepancyBreakdown,
    formatCurrency,
} from '@/lib/api';
import { AnalyticsOverview, TopCodeItem, DiscrepancyPoint } from '@/types/analytics';

// ── Color palettes ─────────────────────────────────────────────────────────────
const RISK_COLORS  = { LOW: '#10b981', MEDIUM: '#f59e0b', HIGH: '#ef4444' };
const PIE_COLORS   = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];
const AREA_STROKE  = '#6366f1';
const AREA_FILL    = '#6366f115';

// ── Shared tooltip ─────────────────────────────────────────────────────────────
const DarkTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    return (
        <div className="glass-card px-3 py-2 text-xs min-w-[120px]">
            <p className="text-slate-400 mb-1">{label}</p>
            {payload.map((p: any, i: number) => (
                <p key={i} style={{ color: p.color ?? '#fff' }} className="font-semibold">
                    {p.name}: {typeof p.value === 'number' && p.name?.toLowerCase().includes('revenue')
                        ? formatCurrency(p.value)
                        : p.value}
                </p>
            ))}
        </div>
    );
};

// ── Stat card ──────────────────────────────────────────────────────────────────
function StatCard({ icon: Icon, value, label, sub, color }: {
    icon: any; value: string; label: string; sub?: string; color: string;
}) {
    return (
        <div className="glass-card px-5 py-4 flex items-center gap-4">
            <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${color}`}>
                <Icon className="w-5 h-5" />
            </div>
            <div className="min-w-0">
                <p className="text-2xl font-extrabold text-white leading-none truncate">{value}</p>
                <p className="text-xs text-slate-500 mt-0.5">{label}</p>
                {sub && <p className="text-[10px] text-slate-600 mt-0.5">{sub}</p>}
            </div>
        </div>
    );
}

// ── Section wrapper ────────────────────────────────────────────────────────────
function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <div className="glass-card p-5 flex flex-col gap-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">{title}</h3>
            {children}
        </div>
    );
}

// ── Skeleton loader ────────────────────────────────────────────────────────────
function Skeleton({ h = 'h-48' }: { h?: string }) {
    return <div className={`${h} bg-white/[0.03] rounded-xl animate-pulse`} />;
}

// ── Main page ──────────────────────────────────────────────────────────────────
export default function AnalyticsPage() {
    const [overview,      setOverview]      = useState<AnalyticsOverview | null>(null);
    const [topCodes,      setTopCodes]      = useState<TopCodeItem[]>([]);
    const [discrepancy,   setDiscrepancy]   = useState<DiscrepancyPoint[]>([]);
    const [loading,       setLoading]       = useState(true);
    const [error,         setError]         = useState<string | null>(null);

    useEffect(() => {
        Promise.all([
            fetchAnalyticsOverview(),
            fetchTopCodes(),
            fetchDiscrepancyBreakdown(),
        ])
            .then(([ov, tc, disc]) => {
                setOverview(ov);
                setTopCodes(tc.codes);
                setDiscrepancy(disc);
            })
            .catch(e => setError(e.message ?? 'Failed to load analytics.'))
            .finally(() => setLoading(false));
    }, []);

    if (error) {
        return (
            <div className="p-10 text-center">
                <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-3" />
                <p className="text-sm text-red-400 font-semibold">Failed to load analytics</p>
                <p className="text-xs text-slate-500 mt-1">{error}</p>
                <p className="text-xs text-slate-600 mt-2">Make sure the backend is running and at least one case has been analysed.</p>
            </div>
        );
    }

    // Risk distribution donut data
    const riskData = overview
        ? Object.entries(overview.risk_distribution).map(([k, v]) => ({ name: k, value: v }))
        : [];

    // Source distribution data
    const sourceData = overview
        ? [
            { name: 'Text Input', value: overview.source_distribution.text_input },
            { name: 'PDF Upload', value: overview.source_distribution.pdf_upload },
          ].filter(d => d.value > 0)
        : [];

    return (
        <div className="min-h-screen flex flex-col">

            {/* Page header */}
            <div className="border-b border-white/[0.06] px-6 py-3 flex items-center gap-2 text-xs text-slate-500 font-medium">
                <BarChart3 className="w-3.5 h-3.5" />
                Analytics
            </div>

            <div className="px-6 py-6 flex-1">
                <div className="max-w-7xl mx-auto space-y-6">

                    <div>
                        <h1 className="text-2xl font-extrabold text-white">Analytics Overview</h1>
                        <p className="text-sm text-slate-400 mt-1">Org-level KPIs, trends, and coding quality metrics across all pipeline runs.</p>
                    </div>

                    {/* ── KPI Cards ─────────────────────────────────────────── */}
                    {loading ? (
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                            {[0,1,2,3].map(i => <Skeleton key={i} h="h-20" />)}
                        </div>
                    ) : overview ? (
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                            <StatCard
                                icon={BarChart3}
                                value={String(overview.total_cases)}
                                label="Total Cases"
                                sub="All time"
                                color="bg-indigo-500/15 text-indigo-400"
                            />
                            <StatCard
                                icon={TrendingUp}
                                value={overview.total_revenue_recovered > 0
                                    ? formatCurrency(overview.total_revenue_recovered)
                                    : '—'}
                                label="Revenue Recovered"
                                sub="Sum of positive deltas"
                                color="bg-emerald-500/15 text-emerald-400"
                            />
                            <StatCard
                                icon={Activity}
                                value={`${overview.avg_confidence}%`}
                                label="Avg AI Confidence"
                                sub="Across all codings"
                                color="bg-violet-500/15 text-violet-400"
                            />
                            <StatCard
                                icon={Shield}
                                value={`${overview.high_risk_rate}%`}
                                label="HIGH Risk Rate"
                                sub="Cases flagged HIGH"
                                color={overview.high_risk_rate > 30 ? 'bg-red-500/15 text-red-400' : 'bg-amber-500/15 text-amber-400'}
                            />
                        </div>
                    ) : null}

                    {/* ── 30-Day Trend ──────────────────────────────────────── */}
                    {loading ? <Skeleton h="h-64" /> : overview ? (
                        <Section title="30-Day Case Volume & Revenue Trend">
                            <div style={{ height: 240 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={overview.trend} margin={{ left: 0, right: 8, top: 4, bottom: 0 }}>
                                        <defs>
                                            <linearGradient id="caseGrad" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.25} />
                                                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                                            </linearGradient>
                                            <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%"  stopColor="#10b981" stopOpacity={0.25} />
                                                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                                        <XAxis
                                            dataKey="date"
                                            tick={{ fill: '#64748b', fontSize: 10 }}
                                            axisLine={false} tickLine={false}
                                            tickFormatter={d => {
                                                const dt = new Date(d);
                                                return `${dt.getDate()}/${dt.getMonth() + 1}`;
                                            }}
                                            interval={4}
                                        />
                                        <YAxis
                                            yAxisId="cases"
                                            tick={{ fill: '#64748b', fontSize: 10 }}
                                            axisLine={false} tickLine={false}
                                            width={28}
                                        />
                                        <YAxis
                                            yAxisId="revenue"
                                            orientation="right"
                                            tick={{ fill: '#64748b', fontSize: 10 }}
                                            axisLine={false} tickLine={false}
                                            width={48}
                                            tickFormatter={v => v > 0 ? `$${(v/1000).toFixed(0)}k` : '0'}
                                        />
                                        <Tooltip content={<DarkTooltip />} />
                                        <Legend
                                            wrapperStyle={{ fontSize: 11, color: '#64748b', paddingTop: 8 }}
                                        />
                                        <Area
                                            yAxisId="cases"
                                            type="monotone"
                                            dataKey="cases"
                                            name="Cases"
                                            stroke="#6366f1"
                                            strokeWidth={2}
                                            fill="url(#caseGrad)"
                                            dot={false}
                                            activeDot={{ r: 4, strokeWidth: 0 }}
                                        />
                                        <Area
                                            yAxisId="revenue"
                                            type="monotone"
                                            dataKey="revenue"
                                            name="Revenue ($)"
                                            stroke="#10b981"
                                            strokeWidth={2}
                                            fill="url(#revGrad)"
                                            dot={false}
                                            activeDot={{ r: 4, strokeWidth: 0 }}
                                        />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        </Section>
                    ) : null}

                    {/* ── Bottom row — Top Codes + Donut Charts ─────────────── */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

                        {/* Top Codes bar chart — spans 2 cols */}
                        {loading ? <div className="lg:col-span-2"><Skeleton h="h-72" /></div> : topCodes.length > 0 ? (
                            <Section title="Top 10 AI-Assigned ICD Codes">
                                <div style={{ height: 260 }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart
                                            data={topCodes}
                                            layout="vertical"
                                            margin={{ left: 0, right: 24, top: 0, bottom: 0 }}
                                        >
                                            <XAxis type="number" hide />
                                            <YAxis
                                                type="category"
                                                dataKey="code"
                                                width={62}
                                                tick={{ fill: '#94a3b8', fontSize: 11, fontFamily: 'monospace', fontWeight: 700 }}
                                                axisLine={false} tickLine={false}
                                            />
                                            <Tooltip
                                                content={({ active, payload }: any) => {
                                                    if (!active || !payload?.length) return null;
                                                    const d = payload[0].payload as TopCodeItem;
                                                    return (
                                                        <div className="glass-card px-3 py-2 text-xs space-y-0.5">
                                                            <p className="font-bold font-mono text-white">{d.code}</p>
                                                            <p className="text-slate-400">Uses: <strong className="text-white">{d.count}</strong></p>
                                                            <p className="text-slate-400">Avg Revenue: <strong className="text-emerald-400">{formatCurrency(d.avg_revenue)}</strong></p>
                                                            <p className="text-slate-400">Avg Risk: <strong className="text-white">{Math.round(d.avg_risk * 100)}%</strong></p>
                                                        </div>
                                                    );
                                                }}
                                                cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                                            />
                                            <Bar dataKey="count" name="Uses" radius={[0, 4, 4, 0]} maxBarSize={22}>
                                                {topCodes.map((_, i) => (
                                                    <Cell
                                                        key={i}
                                                        fill={i === 0 ? '#6366f1' : '#4f46e5'}
                                                        opacity={1 - i * 0.07}
                                                    />
                                                ))}
                                            </Bar>
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </Section>
                        ) : null}

                        {/* Right column stacked — Risk donut + Discrepancy donut */}
                        <div className="flex flex-col gap-5">

                            {/* Risk distribution donut */}
                            {loading ? <Skeleton h="h-40" /> : riskData.some(d => d.value > 0) ? (
                                <Section title="Risk Distribution">
                                    <div style={{ height: 150 }}>
                                        <ResponsiveContainer width="100%" height="100%">
                                            <PieChart>
                                                <Pie
                                                    data={riskData}
                                                    cx="50%" cy="50%"
                                                    innerRadius={42} outerRadius={62}
                                                    paddingAngle={3}
                                                    dataKey="value"
                                                >
                                                    {riskData.map((d, i) => (
                                                        <Cell
                                                            key={d.name}
                                                            fill={RISK_COLORS[d.name as keyof typeof RISK_COLORS] ?? PIE_COLORS[i]}
                                                        />
                                                    ))}
                                                </Pie>
                                                <Tooltip
                                                    content={({ active, payload }: any) =>
                                                        active && payload?.length ? (
                                                            <div className="glass-card px-2.5 py-1.5 text-xs">
                                                                <span style={{ color: payload[0]?.payload?.fill }}>
                                                                    {payload[0].name}: <strong>{payload[0].value}</strong>
                                                                </span>
                                                            </div>
                                                        ) : null
                                                    }
                                                />
                                                <Legend
                                                    iconSize={8}
                                                    wrapperStyle={{ fontSize: 11, color: '#64748b' }}
                                                />
                                            </PieChart>
                                        </ResponsiveContainer>
                                    </div>
                                </Section>
                            ) : null}

                            {/* Discrepancy breakdown */}
                            {loading ? <Skeleton h="h-40" /> : discrepancy.length > 0 ? (
                                <Section title="Discrepancy Types">
                                    <div style={{ height: 150 }}>
                                        <ResponsiveContainer width="100%" height="100%">
                                            <PieChart>
                                                <Pie
                                                    data={discrepancy}
                                                    cx="50%" cy="50%"
                                                    innerRadius={42} outerRadius={62}
                                                    paddingAngle={3}
                                                    dataKey="count"
                                                    nameKey="label"
                                                >
                                                    {discrepancy.map((_, i) => (
                                                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                                                    ))}
                                                </Pie>
                                                <Tooltip
                                                    content={({ active, payload }: any) =>
                                                        active && payload?.length ? (
                                                            <div className="glass-card px-2.5 py-1.5 text-xs">
                                                                <p className="text-slate-300">{payload[0].payload.label}</p>
                                                                <p className="font-bold text-white">{payload[0].value} cases</p>
                                                            </div>
                                                        ) : null
                                                    }
                                                />
                                                <Legend
                                                    iconSize={8}
                                                    formatter={(value: string) => value.length > 14 ? value.slice(0, 14) + '…' : value}
                                                    wrapperStyle={{ fontSize: 10, color: '#64748b' }}
                                                />
                                            </PieChart>
                                        </ResponsiveContainer>
                                    </div>
                                </Section>
                            ) : null}

                        </div>
                    </div>

                    {/* ── Empty state ───────────────────────────────────────── */}
                    {!loading && overview?.total_cases === 0 && (
                        <div className="glass-card p-12 text-center">
                            <BarChart3 className="w-8 h-8 text-slate-600 mx-auto mb-3" />
                            <p className="text-sm font-semibold text-slate-400">No data yet</p>
                            <p className="text-xs text-slate-600 mt-1">Run an analysis from the Analyse page to start seeing trends.</p>
                        </div>
                    )}

                </div>
            </div>
        </div>
    );
}
