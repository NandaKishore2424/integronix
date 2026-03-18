'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { BarChart3, Mail, Lock, ArrowRight, Zap, Eye, EyeOff } from 'lucide-react';
import { supabase } from '@/lib/supabase';

export default function LoginPage() {
    const router = useRouter();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPass, setShowPass] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // FIX FE-BUG-007: try/finally ensures setLoading(false) runs on BOTH success and error
    async function handleLogin(e: React.FormEvent) {
        e.preventDefault();
        setLoading(true); setError('');
        try {
            const { data, error: err } = await supabase.auth.signInWithPassword({ email, password });
            if (err) { setError(err.message); return; }

            if (data.user) {
                const { data: userData } = await supabase.from('users').select('*, organizations(name)').eq('auth_id', data.user.id).single();
                if (userData?.role === 'payer') {
                    router.push('/payer/inbox');
                } else if (userData?.role === 'rcm') {
                    router.push('/hospital/rcm/inbox');
                } else {
                    router.push('/hospital/coder/analyze');
                }
            }
        } finally {
            setLoading(false);
        }
    }

    // FIX FE-BUG-004: Demo credentials from env vars — not hardcoded in source
    // FIX FE-BUG-007: try/finally resets loading on both success and failure
    async function handleDemoAccess() {
        setLoading(true); setError('');
        const demoEmail = process.env.NEXT_PUBLIC_DEMO_EMAIL ?? '';
        const demoPassword = process.env.NEXT_PUBLIC_DEMO_PASSWORD ?? '';
        if (!demoEmail || !demoPassword) {
            setError('Demo credentials not configured. Check NEXT_PUBLIC_DEMO_EMAIL and NEXT_PUBLIC_DEMO_PASSWORD in .env.local.');
            setLoading(false);
            return;
        }
        try {
            const { data, error: err } = await supabase.auth.signInWithPassword({
                email: demoEmail,
                password: demoPassword,
            });
            if (err) { setError('Demo account not configured. Please sign up first.'); return; }

            if (data.user) {
                const { data: userData } = await supabase.from('users').select('*, organizations(name)').eq('auth_id', data.user.id).single();
                if (userData?.role === 'payer') {
                    router.push('/payer/inbox');
                } else if (userData?.role === 'rcm') {
                    router.push('/hospital/rcm/inbox');
                } else {
                    router.push('/hospital/coder/analyze');
                }
            }
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="min-h-screen flex">
            {/* Left panel */}
            <div className="hidden lg:flex w-1/2 bg-gradient-to-br from-indigo-950 via-[#0d1117] to-[#0d1117] flex-col items-center justify-center p-12 border-r border-white/[0.06] relative overflow-hidden">
                <div className="absolute top-0 left-0 w-full h-full pointer-events-none">
                    <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-96 h-96 bg-indigo-600/15 blur-[100px] rounded-full" />
                </div>
                <div className="relative z-10 max-w-sm text-center">
                    <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center mx-auto mb-8 shadow-xl shadow-indigo-900/50">
                        <BarChart3 className="w-7 h-7 text-white" />
                    </div>
                    <h2 className="text-3xl font-extrabold text-white mb-4">Revenue Integrity Platform</h2>
                    <p className="text-slate-400 leading-relaxed mb-10">AI-powered ICD-10-CM coding audit. Catch revenue leakage before it reaches the payer.</p>
                    <div className="space-y-3">
                        {['Multi-tenant hospital architecture', 'Sub-2 second AI analysis', 'Full FHIR R4 interoperability', 'Real-time revenue impact'].map(f => (
                            <div key={f} className="flex items-center gap-3 text-sm text-slate-300">
                                <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
                                {f}
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Right panel — form */}
            <div className="flex-1 flex items-center justify-center p-6">
                <div className="w-full max-w-md">
                    <div className="lg:hidden flex items-center gap-2 mb-8">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
                            <BarChart3 className="w-4 h-4 text-white" />
                        </div>
                        <span className="font-bold text-white">Integronix</span>
                    </div>

                    <h1 className="text-2xl font-extrabold text-white mb-1">Welcome back</h1>
                    <p className="text-slate-400 text-sm mb-8">Sign in to your organisation dashboard</p>

                    <form onSubmit={handleLogin} className="space-y-4">
                        <div>
                            <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Email</label>
                            <div className="relative">
                                <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                                <input
                                    type="email" required value={email} onChange={e => setEmail(e.target.value)}
                                    placeholder="you@hospital.com"
                                    className="clinical-textarea pl-10 h-11"
                                    style={{ resize: 'none', height: '44px', fontFamily: 'inherit' }}
                                />
                            </div>
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Password</label>
                            <div className="relative">
                                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                                <input
                                    type={showPass ? 'text' : 'password'} required value={password} onChange={e => setPassword(e.target.value)}
                                    placeholder="••••••••"
                                    className="clinical-textarea pl-10 pr-10 h-11"
                                    style={{ resize: 'none', height: '44px', fontFamily: 'inherit' }}
                                />
                                <button type="button" onClick={() => setShowPass(p => !p)} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                                    {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                </button>
                            </div>
                        </div>

                        {error && (
                            <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2.5">
                                {error}
                            </div>
                        )}

                        <button type="submit" disabled={loading} className="btn-primary w-full justify-center py-3">
                            {loading ? <span className="animate-spin w-4 h-4 border-2 border-white/30 border-t-white rounded-full" /> : <><ArrowRight className="w-4 h-4" /> Sign In</>}
                        </button>
                    </form>

                    <div className="flex items-center gap-3 my-5">
                        <div className="flex-1 h-px bg-white/[0.07]" />
                        <span className="text-xs text-slate-600">or</span>
                        <div className="flex-1 h-px bg-white/[0.07]" />
                    </div>

                    {/* Demo access button — for presentation */}
                    <button
                        onClick={handleDemoAccess} disabled={loading}
                        className="w-full py-3 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-300 text-sm font-semibold flex items-center justify-center gap-2 hover:bg-amber-500/15 transition-colors"
                    >
                        <Zap className="w-4 h-4" />
                        Demo Access — Quick Preview
                    </button>

                    <p className="text-center text-sm text-slate-500 mt-8">
                        Don&apos;t have an account?{' '}
                        <Link href="/auth/signup" className="text-indigo-400 hover:text-indigo-300 font-medium">
                            Register your organisation
                        </Link>
                    </p>
                </div>
            </div>
        </div>
    );
}
