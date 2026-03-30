'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { BarChart3, ArrowRight, ArrowLeft, Building2, User, Mail, Lock, Eye, EyeOff, MapPin } from 'lucide-react';
import { supabase } from '@/lib/supabase';

type Step = 1 | 2;

export default function SignupPage() {
    const router = useRouter();
    const [step, setStep] = useState<Step>(1);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [showPass, setShowPass] = useState(false);

    // Step 1: org details
    const [orgName, setOrgName] = useState('');
    const [orgType, setOrgType] = useState<'hospital' | 'clinic' | 'rcm_vendor' | 'diagnostic_center'>('hospital');
    const [orgCountry, setOrgCountry] = useState('IN');

    // Step 2: admin account
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPass, setConfirmPass] = useState('');

    function toSlug(name: string) {
        return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    }

    async function handleSignup(e: React.FormEvent) {
        e.preventDefault();
        if (password !== confirmPass) { setError('Passwords do not match.'); return; }
        if (password.length < 8) { setError('Password must be at least 8 characters.'); return; }
        setLoading(true); setError('');

        try {
            // 1. Create Supabase auth user
            const { data: authData, error: authErr } = await supabase.auth.signUp({ email, password });
            if (authErr || !authData.user) throw new Error(authErr?.message ?? 'Sign up failed');

            // 2. Create organization row
            const slug = toSlug(orgName);
            const { data: orgData, error: orgErr } = await supabase
                .from('organizations')
                .insert({ name: orgName, slug, type: orgType, country: orgCountry })
                .select('id')
                .single();
            if (orgErr || !orgData) throw new Error('Could not create organisation. Try a different name.');

            // 3. Create public.users row (admin, no branch)
            const { error: userErr } = await supabase.from('users').insert({
                auth_id: authData.user.id,
                organization_id: orgData.id,
                branch_id: null,
                email,
                full_name: fullName,
                role: 'admin',
            });
            if (userErr) throw new Error('Could not create user profile: ' + userErr.message);

            router.push('/hospital/coder/analyze');
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Something went wrong.');
            setLoading(false);
        }
    }

    return (
        <div className="min-h-screen flex items-center justify-center p-6">
            <div className="absolute inset-0 pointer-events-none">
                <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-amber-500/8 blur-[120px] rounded-full" />
            </div>

            <div className="relative w-full max-w-md">
                {/* Logo */}
                <Link href="/" className="flex items-center gap-2 mb-8 justify-center">
                    <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-400 to-orange-600 flex items-center justify-center">
                        <BarChart3 className="w-5 h-5 text-white" />
                    </div>
                    <span className="text-lg font-bold text-white">CodePerfect Auditor</span>
                </Link>

                {/* Step indicator */}
                <div className="flex items-center gap-2 mb-6 justify-center">
                    {[1, 2].map(s => (
                        <div key={s} className="flex items-center gap-2">
                            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${step >= s ? 'bg-amber-500 text-white' : 'bg-white/[0.08] text-slate-500'}`}>
                                {s}
                            </div>
                            {s < 2 && <div className={`w-12 h-0.5 transition-all ${step > s ? 'bg-amber-500' : 'bg-white/[0.08]'}`} />}
                        </div>
                    ))}
                </div>

                <div className="glass-card p-8">
                    {step === 1 ? (
                        <>
                            <div className="flex items-center gap-3 mb-6">
                                <div className="w-9 h-9 rounded-lg bg-amber-500/15 flex items-center justify-center">
                                    <Building2 className="w-5 h-5 text-amber-400" />
                                </div>
                                <div>
                                    <h1 className="text-lg font-bold text-white">Organisation Details</h1>
                                    <p className="text-xs text-slate-500">Tell us about your organisation</p>
                                </div>
                            </div>

                            <div className="space-y-4">
                                <div>
                                    <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Organisation Name</label>
                                    <div className="relative">
                                        <Building2 className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                                        <input
                                            type="text" value={orgName} onChange={e => setOrgName(e.target.value)} required
                                            placeholder="e.g. Apollo Hospitals Group"
                                            className="clinical-textarea pl-10 h-11"
                                            style={{ resize: 'none', height: '44px', fontFamily: 'inherit' }}
                                        />
                                    </div>
                                </div>

                                <div>
                                    <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Organisation Type</label>
                                    <select
                                        value={orgType} onChange={e => setOrgType(e.target.value as typeof orgType)}
                                        className="clinical-textarea h-11 appearance-none"
                                        style={{ resize: 'none', height: '44px', fontFamily: 'inherit' }}
                                    >
                                        <option value="hospital">Hospital / Hospital Group</option>
                                        <option value="clinic">Clinic / Outpatient Centre</option>
                                        <option value="rcm_vendor">RCM Vendor</option>
                                        <option value="diagnostic_center">Diagnostic Centre</option>
                                        <option value="insurance_payer">Insurance / Payer</option>
                                    </select>
                                </div>

                                <div>
                                    <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Country</label>
                                    <div className="relative">
                                        <MapPin className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                                        <select
                                            value={orgCountry} onChange={e => setOrgCountry(e.target.value)}
                                            className="clinical-textarea pl-10 h-11 appearance-none"
                                            style={{ resize: 'none', height: '44px', fontFamily: 'inherit' }}
                                        >
                                            <option value="IN">India</option>
                                            <option value="US">United States</option>
                                            <option value="UK">United Kingdom</option>
                                            <option value="SG">Singapore</option>
                                            <option value="AE">UAE</option>
                                        </select>
                                    </div>
                                </div>

                                <button
                                    onClick={() => { if (!orgName.trim()) { setError('Please enter organisation name.'); return; } setError(''); setStep(2); }}
                                    className="btn-primary w-full justify-center py-3 mt-2"
                                >
                                    Continue <ArrowRight className="w-4 h-4" />
                                </button>
                                {error && <p className="text-xs text-red-400 text-center">{error}</p>}
                            </div>
                        </>
                    ) : (
                        <form onSubmit={handleSignup}>
                            <div className="flex items-center gap-3 mb-6">
                                <div className="w-9 h-9 rounded-lg bg-amber-500/15 flex items-center justify-center">
                                    <User className="w-5 h-5 text-amber-400" />
                                </div>
                                <div>
                                    <h1 className="text-lg font-bold text-white">Admin Account</h1>
                                    <p className="text-xs text-slate-500">You will be the organisation administrator</p>
                                </div>
                            </div>

                            <div className="space-y-4">
                                <div>
                                    <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Full Name</label>
                                    <div className="relative">
                                        <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                                        <input type="text" required value={fullName} onChange={e => setFullName(e.target.value)}
                                            placeholder="Dr. Jane Smith"
                                            className="clinical-textarea pl-10 h-11"
                                            style={{ resize: 'none', height: '44px', fontFamily: 'inherit' }} />
                                    </div>
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Email</label>
                                    <div className="relative">
                                        <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                                        <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                                            placeholder="admin@hospital.com"
                                            className="clinical-textarea pl-10 h-11"
                                            style={{ resize: 'none', height: '44px', fontFamily: 'inherit' }} />
                                    </div>
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Password</label>
                                    <div className="relative">
                                        <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                                        <input type={showPass ? 'text' : 'password'} required value={password} onChange={e => setPassword(e.target.value)}
                                            placeholder="Min 8 characters"
                                            className="clinical-textarea pl-10 pr-10 h-11"
                                            style={{ resize: 'none', height: '44px', fontFamily: 'inherit' }} />
                                        <button type="button" onClick={() => setShowPass(p => !p)} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                                            {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                        </button>
                                    </div>
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">Confirm Password</label>
                                    <div className="relative">
                                        <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                                        <input type="password" required value={confirmPass} onChange={e => setConfirmPass(e.target.value)}
                                            placeholder="Re-enter password"
                                            className="clinical-textarea pl-10 h-11"
                                            style={{ resize: 'none', height: '44px', fontFamily: 'inherit' }} />
                                    </div>
                                </div>

                                {error && <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2.5">{error}</div>}

                                <div className="flex gap-3 mt-2">
                                    <button type="button" onClick={() => setStep(1)}
                                        className="flex-1 py-3 rounded-xl border border-white/10 text-slate-400 hover:text-white hover:border-white/20 transition-colors text-sm font-medium flex items-center justify-center gap-2">
                                        <ArrowLeft className="w-4 h-4" /> Back
                                    </button>
                                    <button type="submit" disabled={loading} className="btn-primary flex-1 justify-center py-3">
                                        {loading ? <span className="animate-spin w-4 h-4 border-2 border-white/30 border-t-white rounded-full" /> : <>Create Account <ArrowRight className="w-4 h-4" /></>}
                                    </button>
                                </div>
                            </div>
                        </form>
                    )}
                </div>

                <p className="text-center text-sm text-slate-500 mt-6">
                    Already have an account?{' '}
                    <Link href="/auth/login" className="text-amber-400 hover:text-amber-300 font-medium">Sign In</Link>
                </p>
            </div>
        </div>
    );
}
