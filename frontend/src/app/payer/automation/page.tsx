'use client';

import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/components/AuthProvider';
import { useRouter } from 'next/navigation';
import {
    fetchPayerByOrg,
    getPayerSettings,
    updatePayerSettings,
    type PayerSettings,
    type CustomRule,
    type CustomRuleType,
} from '@/lib/api';
import {
    ShieldCheck,
    ShieldOff,
    Plus,
    Trash2,
    Save,
    AlertTriangle,
    CheckCircle2,
    Loader2,
    ChevronDown,
} from 'lucide-react';

// ── helpers ───────────────────────────────────────────────────────────────────

function pct(v: number) {
    return Math.round(v * 100);
}

const RULE_LABELS: Record<CustomRuleType, string> = {
    max_amount: 'Max Bill Amount (₹)',
    exclude_cpt_prefix: 'Block CPT Code Prefix',
    require_min_age: 'Minimum Patient Age (yrs)',
    require_max_age: 'Maximum Patient Age (yrs)',
};

function emptyRule(): CustomRule {
    return { rule_type: 'max_amount', label: '', threshold: undefined };
}

// ── sub components ────────────────────────────────────────────────────────────

function Toggle({
    checked,
    onChange,
    label,
    description,
}: {
    checked: boolean;
    onChange: (v: boolean) => void;
    label: string;
    description?: string;
}) {
    return (
        <label className="flex items-start gap-4 cursor-pointer group">
            <div className="relative mt-0.5 shrink-0">
                <input
                    type="checkbox"
                    className="sr-only"
                    checked={checked}
                    onChange={e => onChange(e.target.checked)}
                />
                <div
                    className={`w-11 h-6 rounded-full transition-colors ${
                        checked ? 'bg-emerald-500' : 'bg-slate-700'
                    }`}
                />
                <div
                    className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
                        checked ? 'translate-x-5' : 'translate-x-0'
                    }`}
                />
            </div>
            <div>
                <p className="text-sm font-medium text-slate-200 group-hover:text-white transition-colors">
                    {label}
                </p>
                {description && <p className="text-xs text-slate-500 mt-0.5">{description}</p>}
            </div>
        </label>
    );
}

function PercentSlider({
    label,
    description,
    value,
    onChange,
    min = 0,
    max = 100,
    color = 'emerald',
}: {
    label: string;
    description?: string;
    value: number;
    onChange: (v: number) => void;
    min?: number;
    max?: number;
    color?: 'emerald' | 'red';
}) {
    const pctValue = Math.round(value * 100);
    return (
        <div>
            <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-medium text-slate-300">{label}</span>
                <span
                    className={`text-sm font-bold tabular-nums ${
                        color === 'red' ? 'text-red-400' : 'text-emerald-400'
                    }`}
                >
                    {pctValue}%
                </span>
            </div>
            {description && <p className="text-xs text-slate-500 mb-2">{description}</p>}
            <input
                type="range"
                min={min}
                max={max}
                value={pctValue}
                onChange={e => onChange(parseInt(e.target.value) / 100)}
                className="w-full h-1.5 rounded-full appearance-none bg-slate-700 accent-emerald-500 cursor-pointer"
            />
        </div>
    );
}

// ── main page ─────────────────────────────────────────────────────────────────

export default function AutomationPage() {
    const { org, orgUser, loading } = useAuth();
    const router = useRouter();

    const [settings, setSettings] = useState<PayerSettings | null>(null);
    const [fetching, setFetching] = useState(true);
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Redirect non-admin users
    useEffect(() => {
        if (!loading && orgUser && orgUser.role !== 'admin') {
            router.replace('/payer/inbox');
        }
    }, [loading, orgUser, router]);

    // Load settings on mount
    const loadSettings = useCallback(async () => {
        if (!org?.id) return;
        setFetching(true);
        setError(null);
        try {
            const payer = await fetchPayerByOrg(org.id);
            if (!payer) throw new Error("No payer record found for this organization.");
            
            const data = await getPayerSettings(payer.id);
            setSettings(data);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to load settings.');
        } finally {
            setFetching(false);
        }
    }, [org?.id]);

    useEffect(() => { loadSettings(); }, [loadSettings]);

    const handleSave = async () => {
        if (!settings || !org?.id) return;
        setSaving(true);
        setError(null);
        setSaved(false);
        try {
            const { payer_id: _, ...payload } = settings;
            const updated = await updatePayerSettings(settings.payer_id, payload);
            setSettings(updated);
            setSaved(true);
            setTimeout(() => setSaved(false), 3500);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to save settings.');
        } finally {
            setSaving(false);
        }
    };

    // Typed partial-update helper
    const update = <K extends keyof PayerSettings>(key: K, value: PayerSettings[K]) => {
        setSettings(prev => (prev ? { ...prev, [key]: value } : prev));
        setSaved(false);
    };

    // Custom rules helpers
    const addRule = () => {
        if (!settings) return;
        update('auto_approve_custom_rules', [...settings.auto_approve_custom_rules, emptyRule()]);
    };

    const removeRule = (idx: number) => {
        if (!settings) return;
        update('auto_approve_custom_rules', settings.auto_approve_custom_rules.filter((_, i) => i !== idx));
    };

    const updateRule = (idx: number, patch: Partial<CustomRule>) => {
        if (!settings) return;
        const updated = settings.auto_approve_custom_rules.map((r, i) =>
            i === idx ? { ...r, ...patch } : r
        );
        update('auto_approve_custom_rules', updated);
    };

    // ── render ─────────────────────────────────────────────────────────────

    if (fetching) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <Loader2 className="w-7 h-7 text-emerald-500 animate-spin" />
                    <p className="text-sm text-slate-500">Loading automation settings…</p>
                </div>
            </div>
        );
    }

    if (!settings) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-center">
                    <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
                    <p className="text-sm text-slate-400">{error ?? 'Could not load settings.'}</p>
                    <button
                        onClick={loadSettings}
                        className="mt-4 text-sm text-emerald-400 hover:text-emerald-300 underline"
                    >
                        Try again
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen p-8 max-w-3xl mx-auto">
            {/* ── Header ── */}
            <div className="mb-8">
                <h1 className="text-2xl font-bold text-white tracking-tight">Automation Settings</h1>
                <p className="text-sm text-slate-400 mt-1">
                    Configure how claims are automatically adjudicated for{' '}
                    <span className="text-emerald-400 font-medium">{org?.name}</span>.
                </p>
            </div>

            {/* ── Toast feedback ── */}
            {error && (
                <div className="mb-6 flex items-center gap-2.5 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                    {error}
                </div>
            )}
            {saved && (
                <div className="mb-6 flex items-center gap-2.5 px-4 py-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm">
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                    Settings saved successfully.
                </div>
            )}

            {/* ── Card: Master Toggle ── */}
            <section className="mb-5 p-6 rounded-2xl bg-slate-900 border border-white/[0.06]">
                <div className="flex items-center gap-3 mb-5">
                    {settings.auto_approve_enabled
                        ? <ShieldCheck className="w-5 h-5 text-emerald-400" />
                        : <ShieldOff className="w-5 h-5 text-slate-500" />
                    }
                    <h2 className="text-base font-semibold text-white">Auto-Adjudication</h2>
                </div>
                <Toggle
                    checked={settings.auto_approve_enabled}
                    onChange={v => update('auto_approve_enabled', v)}
                    label="Enable automatic claim approval"
                    description="When active, low-risk claims that pass all gates below are approved instantly without manual review."
                />
            </section>

            {/* ── Card: Global Thresholds ── */}
            <section className="mb-5 p-6 rounded-2xl bg-slate-900 border border-white/[0.06] space-y-6">
                <h2 className="text-base font-semibold text-white">Global AI Thresholds</h2>

                <PercentSlider
                    label="Minimum AI Confidence"
                    description="Claims with coding confidence below this percentage go to manual review."
                    value={settings.auto_approve_confidence_min}
                    onChange={v => update('auto_approve_confidence_min', v)}
                />

                <PercentSlider
                    label="Maximum Risk Score"
                    description="Claims with a fraud/denial risk score above this percentage go to manual review."
                    value={settings.auto_approve_max_risk}
                    onChange={v => update('auto_approve_max_risk', v)}
                    color="red"
                />

                <PercentSlider
                    label="Payer Responsibility"
                    description="Percentage of the approved amount that your organisation bears. Patient pays the remainder."
                    value={settings.auto_approve_payer_responsibility_pct}
                    onChange={v => update('auto_approve_payer_responsibility_pct', v)}
                />
            </section>

            {/* ── Card: Strict Gates ── */}
            <section className="mb-5 p-6 rounded-2xl bg-slate-900 border border-white/[0.06] space-y-5">
                <h2 className="text-base font-semibold text-white">Required Demographics</h2>
                <Toggle
                    checked={settings.auto_approve_requires_patient_dob}
                    onChange={v => update('auto_approve_requires_patient_dob', v)}
                    label="Require Patient Date of Birth"
                    description="Claims submitted without a DOB will always escalate to manual review."
                />
                <Toggle
                    checked={settings.auto_approve_requires_patient_sex}
                    onChange={v => update('auto_approve_requires_patient_sex', v)}
                    label="Require Patient Sex"
                    description="Claims submitted without a biological sex field will always escalate to manual review."
                />
            </section>

            {/* ── Card: Custom Rules ── */}
            <section className="mb-8 p-6 rounded-2xl bg-slate-900 border border-white/[0.06]">
                <div className="flex items-center justify-between mb-5">
                    <h2 className="text-base font-semibold text-white">Custom Rules</h2>
                    <button
                        onClick={addRule}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/20 transition-colors"
                    >
                        <Plus className="w-3.5 h-3.5" />
                        Add Rule
                    </button>
                </div>

                {settings.auto_approve_custom_rules.length === 0 ? (
                    <p className="text-sm text-slate-500 text-center py-6">
                        No custom rules defined. All compliant claims that pass the AI thresholds above will be auto-approved.
                    </p>
                ) : (
                    <div className="space-y-3">
                        {settings.auto_approve_custom_rules.map((rule, idx) => (
                            <div
                                key={idx}
                                className="flex gap-3 items-start p-4 rounded-xl bg-slate-800/60 border border-white/[0.05]"
                            >
                                {/* Rule type selector */}
                                <div className="flex-1 space-y-3">
                                    <div className="flex gap-3">
                                        <div className="relative flex-1">
                                            <select
                                                value={rule.rule_type}
                                                onChange={e => updateRule(idx, {
                                                    rule_type: e.target.value as CustomRuleType,
                                                    threshold: undefined,
                                                    code_prefix: undefined,
                                                    min_age: undefined,
                                                    max_age: undefined,
                                                })}
                                                className="w-full appearance-none bg-slate-700 border border-white/[0.08] text-slate-200 text-sm rounded-lg px-3 py-2 pr-8 focus:outline-none focus:border-emerald-500/50"
                                            >
                                                {(Object.keys(RULE_LABELS) as CustomRuleType[]).map(rt => (
                                                    <option key={rt} value={rt}>{RULE_LABELS[rt]}</option>
                                                ))}
                                            </select>
                                            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-2.5 pointer-events-none" />
                                        </div>
                                    </div>

                                    <input
                                        type="text"
                                        placeholder="Label (e.g. 'No auto-approve above ₹5 lakh')"
                                        value={rule.label}
                                        onChange={e => updateRule(idx, { label: e.target.value })}
                                        className="w-full bg-slate-700 border border-white/[0.08] text-slate-200 text-sm rounded-lg px-3 py-2 placeholder-slate-600 focus:outline-none focus:border-emerald-500/50"
                                    />

                                    {/* Dynamic value field based on rule_type */}
                                    {rule.rule_type === 'max_amount' && (
                                        <input
                                            type="number"
                                            min={0}
                                            placeholder="Threshold in ₹ (e.g. 500000)"
                                            value={rule.threshold ?? ''}
                                            onChange={e => updateRule(idx, { threshold: parseFloat(e.target.value) || undefined })}
                                            className="w-full bg-slate-700 border border-white/[0.08] text-slate-200 text-sm rounded-lg px-3 py-2 placeholder-slate-600 focus:outline-none focus:border-emerald-500/50"
                                        />
                                    )}
                                    {rule.rule_type === 'exclude_cpt_prefix' && (
                                        <input
                                            type="text"
                                            placeholder="CPT prefix (e.g. '274' blocks all arthroplasties)"
                                            value={rule.code_prefix ?? ''}
                                            onChange={e => updateRule(idx, { code_prefix: e.target.value })}
                                            className="w-full bg-slate-700 border border-white/[0.08] text-slate-200 text-sm rounded-lg px-3 py-2 placeholder-slate-600 focus:outline-none focus:border-emerald-500/50"
                                        />
                                    )}
                                    {rule.rule_type === 'require_min_age' && (
                                        <input
                                            type="number"
                                            min={0}
                                            placeholder="Minimum age in years (e.g. 18)"
                                            value={rule.min_age ?? ''}
                                            onChange={e => updateRule(idx, { min_age: parseInt(e.target.value) || undefined })}
                                            className="w-full bg-slate-700 border border-white/[0.08] text-slate-200 text-sm rounded-lg px-3 py-2 placeholder-slate-600 focus:outline-none focus:border-emerald-500/50"
                                        />
                                    )}
                                    {rule.rule_type === 'require_max_age' && (
                                        <input
                                            type="number"
                                            min={0}
                                            placeholder="Maximum age in years (e.g. 70)"
                                            value={rule.max_age ?? ''}
                                            onChange={e => updateRule(idx, { max_age: parseInt(e.target.value) || undefined })}
                                            className="w-full bg-slate-700 border border-white/[0.08] text-slate-200 text-sm rounded-lg px-3 py-2 placeholder-slate-600 focus:outline-none focus:border-emerald-500/50"
                                        />
                                    )}
                                </div>

                                {/* Remove button */}
                                <button
                                    onClick={() => removeRule(idx)}
                                    className="mt-1 p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                                    title="Remove rule"
                                >
                                    <Trash2 className="w-4 h-4" />
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </section>

            {/* ── Save Button ── */}
            <div className="flex justify-end">
                <button
                    onClick={handleSave}
                    disabled={saving}
                    className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-60 disabled:cursor-not-allowed text-white text-sm font-semibold transition-colors shadow-lg shadow-emerald-500/20"
                >
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    {saving ? 'Saving…' : 'Save Settings'}
                </button>
            </div>
        </div>
    );
}
