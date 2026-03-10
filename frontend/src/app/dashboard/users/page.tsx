'use client';

import { useState, useEffect, useCallback } from 'react';
import { Plus, Users, Loader2, X, User, Mail, Lock, Eye, EyeOff } from 'lucide-react';
import { supabase, Branch, OrgUser, UserRole } from '@/lib/supabase';
import { useAuth } from '@/components/AuthProvider';

export default function UsersPage() {
    const { orgUser } = useAuth();
    const [users, setUsers] = useState<OrgUser[]>([]);
    const [branches, setBranches] = useState<Branch[]>([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [showPass, setShowPass] = useState(false);
    const [form, setForm] = useState({
        full_name: '', email: '', password: '', role: 'coder' as UserRole, branch_id: '',
    });

    const fetchData = useCallback(async () => {
        if (!orgUser) return;
        setLoading(true);
        const [{ data: usersData }, { data: branchData }] = await Promise.all([
            supabase.from('users').select('*').eq('organization_id', orgUser.organization_id).order('created_at'),
            supabase.from('branches').select('*').eq('organization_id', orgUser.organization_id).order('name'),
        ]);
        setUsers((usersData as OrgUser[]) ?? []);
        setBranches((branchData as Branch[]) ?? []);
        setLoading(false);
    }, [orgUser]);

    useEffect(() => { fetchData(); }, [fetchData]);

    async function createUser(e: React.FormEvent) {
        e.preventDefault();
        if (!orgUser) return;
        if (form.password.length < 8) { setError('Password must be at least 8 characters.'); return; }
        setSaving(true); setError('');
        try {
            // Create auth user via Supabase Auth (note: this requires service role in prod)
            // For demo, we use signUp which works with anon key
            const { data: authData, error: authErr } = await supabase.auth.signUp({
                email: form.email,
                password: form.password,
                options: { data: { full_name: form.full_name } }
            });
            if (authErr || !authData.user) throw new Error(authErr?.message ?? 'Auth signup failed');

            const { error: userErr } = await supabase.from('users').insert({
                auth_id: authData.user.id,
                organization_id: orgUser.organization_id,
                branch_id: form.branch_id || null,
                email: form.email,
                full_name: form.full_name,
                role: form.role,
            });
            if (userErr) throw new Error(userErr.message);

            setForm({ full_name: '', email: '', password: '', role: 'coder', branch_id: '' });
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
            auditor: 'bg-blue-500/15 text-blue-400 border-blue-500/25',
            coder: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25',
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
                        <h1 className="text-2xl font-extrabold text-white mb-1">Users</h1>
                        <p className="text-sm text-slate-400">Manage team members, roles, and branch assignments.</p>
                    </div>
                    <button onClick={() => setShowModal(true)} className="btn-primary flex items-center gap-2 py-2.5 px-5">
                        <Plus className="w-4 h-4" /> Add User
                    </button>
                </div>
            </div>

            <div className="px-8 py-6">
                {loading ? (
                    <div className="flex justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-indigo-400" /></div>
                ) : (
                    <div className="glass-card overflow-hidden">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-white/[0.06]">
                                    {['Name', 'Email', 'Role', 'Branch'].map(h => (
                                        <th key={h} className="text-left px-5 py-3 text-[10px] font-semibold text-slate-500 uppercase tracking-widest">{h}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {users.map((u, i) => {
                                    const branch = branches.find(b => b.id === u.branch_id);
                                    return (
                                        <tr key={u.id} className={`border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors ${i === users.length - 1 ? 'border-none' : ''}`}>
                                            <td className="px-5 py-3.5">
                                                <div className="flex items-center gap-3">
                                                    <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
                                                        {u.full_name.charAt(0).toUpperCase()}
                                                    </div>
                                                    <span className="font-medium text-white text-sm">{u.full_name}</span>
                                                </div>
                                            </td>
                                            <td className="px-5 py-3.5 text-slate-400 font-mono text-xs">{u.email}</td>
                                            <td className="px-5 py-3.5">
                                                <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full border ${roleBadge(u.role)}`}>
                                                    {u.role}
                                                </span>
                                            </td>
                                            <td className="px-5 py-3.5 text-slate-400 text-xs">
                                                {branch ? branch.name : <span className="text-slate-600 italic">Org-wide (Admin)</span>}
                                            </td>
                                        </tr>
                                    );
                                })}
                                {users.length === 0 && (
                                    <tr><td colSpan={4} className="text-center py-12 text-slate-500">No users yet</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* Add User Modal */}
            {showModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
                    <div className="glass-card w-full max-w-md p-6 animate-slide-up max-h-[90vh] overflow-y-auto">
                        <div className="flex items-center justify-between mb-5">
                            <h2 className="font-bold text-white text-lg">Add User</h2>
                            <button onClick={() => { setShowModal(false); setError(''); }} className="text-slate-500 hover:text-white"><X className="w-5 h-5" /></button>
                        </div>
                        <form onSubmit={createUser} className="space-y-4">
                            <div>
                                <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Full Name</label>
                                <div className="relative">
                                    <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                                    <input type="text" required value={form.full_name} onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
                                        placeholder="Dr. Jane Smith" className="clinical-textarea pl-10 h-10"
                                        style={{ resize: 'none', height: '40px', fontFamily: 'inherit' }} />
                                </div>
                            </div>
                            <div>
                                <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Email</label>
                                <div className="relative">
                                    <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                                    <input type="email" required value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                                        placeholder="user@hospital.com" className="clinical-textarea pl-10 h-10"
                                        style={{ resize: 'none', height: '40px', fontFamily: 'inherit' }} />
                                </div>
                            </div>
                            <div>
                                <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Password</label>
                                <div className="relative">
                                    <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                                    <input type={showPass ? 'text' : 'password'} required value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                                        placeholder="Min 8 characters" className="clinical-textarea pl-10 pr-10 h-10"
                                        style={{ resize: 'none', height: '40px', fontFamily: 'inherit' }} />
                                    <button type="button" onClick={() => setShowPass(p => !p)} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                                        {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                    </button>
                                </div>
                            </div>
                            <div>
                                <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Role</label>
                                <select value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value as UserRole }))}
                                    className="clinical-textarea h-10 appearance-none" style={{ resize: 'none', height: '40px', fontFamily: 'inherit' }}>
                                    <option value="coder">Coder — Submit & view own branch cases</option>
                                    <option value="auditor">Auditor — Read-only across organisation</option>
                                    <option value="admin">Admin — Full access</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Branch Assignment</label>
                                <select value={form.branch_id} onChange={e => setForm(f => ({ ...f, branch_id: e.target.value }))}
                                    className="clinical-textarea h-10 appearance-none" style={{ resize: 'none', height: '40px', fontFamily: 'inherit' }}>
                                    <option value="">Org-wide (no branch restriction)</option>
                                    {branches.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
                                </select>
                            </div>
                            {error && <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</p>}
                            <div className="flex gap-3 pt-1">
                                <button type="button" onClick={() => { setShowModal(false); setError(''); }}
                                    className="flex-1 py-2.5 rounded-xl border border-white/10 text-slate-400 hover:text-white text-sm font-medium transition-colors">Cancel</button>
                                <button type="submit" disabled={saving} className="btn-primary flex-1 justify-center py-2.5">
                                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create User'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
