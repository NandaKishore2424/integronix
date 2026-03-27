'use client';

import { useState, useEffect, useCallback } from 'react';
import { Plus, Users, Loader2, X, User, Mail, Lock, Eye, EyeOff } from 'lucide-react';
import { supabase, OrgUser, UserRole } from '@/lib/supabase';
import { useAuth } from '@/components/AuthProvider';

export default function PayerUsersPage() {
    const { orgUser } = useAuth();
    const [users, setUsers] = useState<OrgUser[]>([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [showPass, setShowPass] = useState(false);
    const [form, setForm] = useState({
        full_name: '', email: '', password: '', role: 'payer' as UserRole,
    });

    const fetchData = useCallback(async () => {
        if (!orgUser) return;
        setLoading(true);
        const { data: usersData } = await supabase
            .from('users')
            .select('*')
            .eq('organization_id', orgUser.organization_id)
            .order('created_at');
            
        setUsers((usersData as OrgUser[]) ?? []);
        setLoading(false);
    }, [orgUser]);

    useEffect(() => { fetchData(); }, [fetchData]);

    async function createUser(e: React.FormEvent) {
        e.preventDefault();
        if (!orgUser) return;
        if (form.password.length < 8) { setError('Password must be at least 8 characters.'); return; }
        setSaving(true); setError('');
        try {
            // Create auth user via Supabase Auth
            const { data: authData, error: authErr } = await supabase.auth.signUp({
                email: form.email,
                password: form.password,
                options: { data: { full_name: form.full_name } }
            });
            if (authErr || !authData.user) throw new Error(authErr?.message ?? 'Auth signup failed');

            const { error: userErr } = await supabase.from('users').insert({
                auth_id: authData.user.id,
                organization_id: orgUser.organization_id,
                email: form.email,
                full_name: form.full_name,
                role: form.role,
            });
            if (userErr) throw new Error(userErr.message);

            setForm({ full_name: '', email: '', password: '', role: 'payer' });
            setShowModal(false);
            fetchData();
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to create user');
        }
        setSaving(false);
    }

    const roleBadge = (role: string) => {
        const map: Record<string, string> = {
            admin: 'bg-amber-500/15 text-amber-400 border-amber-500/25',
            payer: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25',
        };
        return map[role] ?? 'bg-slate-500/15 text-slate-400';
    };

    if (orgUser?.role !== 'admin') {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-center">
                    <Users className="w-10 h-10 text-slate-600 mx-auto mb-3" />
                    <p className="text-slate-400 font-medium">Admin access required</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen">
            <div className="border-b border-white/[0.06] px-8 py-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-extrabold text-white mb-1">Payer Staff</h1>
                        <p className="text-sm text-slate-400">Manage claims reviewers, analysts, and fellow admins.</p>
                    </div>
                    <button onClick={() => setShowModal(true)} className="btn-primary flex items-center gap-2 py-2.5 px-5">
                        <Plus className="w-4 h-4" /> Add Staff Profile
                    </button>
                </div>
            </div>

            <div className="px-8 py-6">
                {loading ? (
                    <div className="flex justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-amber-400" /></div>
                ) : (
                    <div className="glass-card overflow-hidden">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-white/[0.06]">
                                    {['Name', 'Email', 'Role'].map(h => (
                                        <th key={h} className="text-left px-5 py-3 text-[10px] font-semibold text-slate-500 uppercase tracking-widest">{h}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {users.map((u, i) => (
                                    <tr key={u.id} className={`border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors ${i === users.length - 1 ? 'border-none' : ''}`}>
                                        <td className="px-5 py-3.5">
                                            <div className="flex items-center gap-3">
                                                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
                                                    {u.full_name.charAt(0).toUpperCase()}
                                                </div>
                                                <span className="font-medium text-white text-sm">{u.full_name}</span>
                                            </div>
                                        </td>
                                        <td className="px-5 py-3.5 text-slate-400 font-mono text-xs">{u.email}</td>
                                        <td className="px-5 py-3.5">
                                            <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full border ${roleBadge(u.role)}`}>
                                                {u.role === 'payer' ? 'Claims Reviewer' : u.role}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                                {users.length === 0 && (
                                    <tr><td colSpan={3} className="text-center py-12 text-slate-500">No users yet</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* Add User Modal */}
            {showModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
                    <div className="w-full max-w-md rounded-2xl bg-slate-900 border border-white/10 shadow-2xl animate-slide-up max-h-[90vh] overflow-y-auto">
                        <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-white/[0.07]">
                            <div>
                                <h2 className="font-bold text-white text-lg">Add Team Member</h2>
                                <p className="text-xs text-slate-400 mt-0.5">Create a login for a new reviewer or admin.</p>
                            </div>
                            <button onClick={() => { setShowModal(false); setError(''); }} className="p-1.5 rounded-lg text-slate-500 hover:text-white hover:bg-white/[0.06] transition-colors"><X className="w-5 h-5" /></button>
                        </div>

                        <form onSubmit={createUser} className="px-6 py-5 space-y-4">
                            <div>
                                <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">Full Name</label>
                                <div className="relative">
                                    <User className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                                    <input type="text" required value={form.full_name} onChange={e => setForm({ ...form, full_name: e.target.value })}
                                        className="w-full h-11 bg-slate-800 border-2 border-slate-700/50 rounded-xl pl-10 pr-4 text-sm text-slate-200 outline-none focus:border-amber-500/50"
                                        placeholder="Jane Doe"
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">Email Address</label>
                                <div className="relative">
                                    <Mail className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                                    <input type="email" required value={form.email} onChange={e => setForm({ ...form, email: e.target.value })}
                                        className="w-full h-11 bg-slate-800 border-2 border-slate-700/50 rounded-xl pl-10 pr-4 text-sm text-slate-200 outline-none focus:border-amber-500/50"
                                        placeholder="jane.doe@insurance.com"
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">Password</label>
                                <div className="relative">
                                    <Lock className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                                    <input type={showPass ? 'text' : 'password'} required value={form.password} onChange={e => setForm({ ...form, password: e.target.value })}
                                        className="w-full h-11 bg-slate-800 border-2 border-slate-700/50 rounded-xl pl-10 pr-10 text-sm text-slate-200 outline-none focus:border-amber-500/50"
                                        placeholder="••••••••"
                                        minLength={8}
                                    />
                                    <button type="button" onClick={() => setShowPass(!showPass)} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                                        {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                    </button>
                                </div>
                            </div>

                            <div>
                                <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">System Role</label>
                                <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value as UserRole })}
                                    className="w-full h-11 bg-slate-800 border-2 border-slate-700/50 rounded-xl px-4 text-sm text-slate-200 outline-none focus:border-amber-500/50">
                                    <option value="payer">Claims Reviewer</option>
                                    <option value="admin">Administrator</option>
                                </select>
                            </div>

                            {error && (
                                <div className="py-2.5 px-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm font-medium">
                                    {error}
                                </div>
                            )}

                            <div className="pt-2">
                                <button type="submit" disabled={saving} className="btn-primary w-full justify-center h-11">
                                    {saving ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Create Account'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
