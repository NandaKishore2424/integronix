'use client';

import { useState, useEffect, useCallback } from 'react';
import { Plus, GitBranch, MapPin, Loader2, X, Building2 } from 'lucide-react';
import { supabase, Branch } from '@/lib/supabase';
import { useAuth } from '@/components/AuthProvider';

export default function BranchesPage() {
    const { orgUser } = useAuth();
    const [branches, setBranches] = useState<Branch[]>([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [form, setForm] = useState({ name: '', code: '', city: '', state: '' });

    const fetchBranches = useCallback(async () => {
        if (!orgUser) return;
        setLoading(true);
        const { data } = await supabase
            .from('branches')
            .select('*')
            .eq('organization_id', orgUser.organization_id)
            .order('created_at', { ascending: false });
        setBranches((data as Branch[]) ?? []);
        setLoading(false);
    }, [orgUser]);

    useEffect(() => { fetchBranches(); }, [fetchBranches]);

    async function createBranch(e: React.FormEvent) {
        e.preventDefault();
        if (!orgUser) return;
        if (!form.name.trim()) { setError('Branch name is required.'); return; }
        setSaving(true); setError('');
        const { error: err } = await supabase.from('branches').insert({
            organization_id: orgUser.organization_id,
            name: form.name.trim(),
            code: form.code.trim() || null,
            city: form.city.trim() || null,
            state: form.state.trim() || null,
        });
        if (err) { setError(err.message); setSaving(false); return; }
        setForm({ name: '', code: '', city: '', state: '' });
        setShowModal(false);
        fetchBranches();
        setSaving(false);
    }

    if (orgUser?.role !== 'admin') {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-center">
                    <GitBranch className="w-10 h-10 text-slate-600 mx-auto mb-3" />
                    <p className="text-slate-400 font-medium">Admin access required</p>
                    <p className="text-sm text-slate-600 mt-1">Only organisation admins can manage branches.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen">
            {/* Header */}
            <div className="border-b border-white/[0.06] px-8 py-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-extrabold text-white mb-1">Branches</h1>
                        <p className="text-sm text-slate-400">Manage physical locations and departments within your organisation.</p>
                    </div>
                    <button onClick={() => setShowModal(true)} className="btn-primary flex items-center gap-2 py-2.5 px-5">
                        <Plus className="w-4 h-4" /> Add Branch
                    </button>
                </div>
            </div>

            <div className="px-8 py-6">
                {loading ? (
                    <div className="flex justify-center py-16">
                        <Loader2 className="w-6 h-6 animate-spin text-amber-400" />
                    </div>
                ) : branches.length === 0 ? (
                    <div className="text-center py-16">
                        <div className="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mx-auto mb-4">
                            <Building2 className="w-7 h-7 text-amber-400" />
                        </div>
                        <h3 className="font-semibold text-white mb-1">No branches yet</h3>
                        <p className="text-sm text-slate-400 mb-5">Add your first branch to start assigning users and cases.</p>
                        <button onClick={() => setShowModal(true)} className="btn-primary flex items-center gap-2 mx-auto py-2.5 px-5">
                            <Plus className="w-4 h-4" /> Add First Branch
                        </button>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        {branches.map(b => (
                            <div key={b.id} className="glass-card p-5">
                                <div className="flex items-start gap-3">
                                    <div className="w-9 h-9 rounded-lg bg-amber-500/15 border border-amber-500/20 flex items-center justify-center shrink-0">
                                        <GitBranch className="w-4 h-4 text-amber-400" />
                                    </div>
                                    <div className="min-w-0">
                                        <h3 className="font-semibold text-white text-sm truncate">{b.name}</h3>
                                        {b.code && <p className="text-xs font-mono text-slate-500 mt-0.5">{b.code}</p>}
                                        {(b.city || b.state) && (
                                            <div className="flex items-center gap-1 mt-2 text-xs text-slate-400">
                                                <MapPin className="w-3 h-3" />
                                                {[b.city, b.state].filter(Boolean).join(', ')}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Add Branch Modal */}
            {showModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
                    <div className="glass-card w-full max-w-md p-6 animate-slide-up">
                        <div className="flex items-center justify-between mb-5">
                            <h2 className="font-bold text-white text-lg">Add Branch</h2>
                            <button onClick={() => { setShowModal(false); setError(''); }} className="text-slate-500 hover:text-white">
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        <form onSubmit={createBranch} className="space-y-4">
                            {[
                                { label: 'Branch Name *', key: 'name', placeholder: 'e.g. Main Campus — Cardiology' },
                                { label: 'Branch Code', key: 'code', placeholder: 'e.g. APL-CARD (optional)' },
                                { label: 'City', key: 'city', placeholder: 'e.g. Chennai (optional)' },
                                { label: 'State', key: 'state', placeholder: 'e.g. Tamil Nadu (optional)' },
                            ].map(field => (
                                <div key={field.key}>
                                    <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">{field.label}</label>
                                    <input
                                        type="text"
                                        value={form[field.key as keyof typeof form]}
                                        onChange={e => setForm(f => ({ ...f, [field.key]: e.target.value }))}
                                        placeholder={field.placeholder}
                                        className="clinical-textarea h-10"
                                        style={{ resize: 'none', height: '40px', fontFamily: 'inherit' }}
                                    />
                                </div>
                            ))}
                            {error && <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</p>}
                            <div className="flex gap-3 pt-1">
                                <button type="button" onClick={() => { setShowModal(false); setError(''); }}
                                    className="flex-1 py-2.5 rounded-xl border border-white/10 text-slate-400 hover:text-white text-sm font-medium transition-colors">
                                    Cancel
                                </button>
                                <button type="submit" disabled={saving} className="btn-primary flex-1 justify-center py-2.5">
                                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create Branch'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
