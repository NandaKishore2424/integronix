'use client';

import Link from 'next/link';
import { ShieldOff, ArrowLeft } from 'lucide-react';
import { useAuth } from '@/components/AuthProvider';

export default function ForbiddenPage() {
    const { orgUser } = useAuth();

    // Redirect path based on role – takes them back to their rightful home
    const homeHref =
        orgUser?.role === 'payer' ? '/payer/inbox' :
        orgUser?.role === 'rcm'   ? '/hospital/rcm/claims' :
        '/hospital/coder/analyze';

    return (
        <div className="min-h-screen flex items-center justify-center bg-slate-950">
            {/* Ambient background glow */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-red-600/10 rounded-full blur-3xl" />
            </div>

            <div className="relative z-10 text-center max-w-md mx-auto px-6">
                {/* Icon */}
                <div className="w-20 h-20 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto mb-6">
                    <ShieldOff className="w-10 h-10 text-red-400" />
                </div>

                {/* Error code */}
                <div className="text-[80px] font-black text-white/5 leading-none select-none mb-2">
                    403
                </div>

                {/* Message */}
                <h1 className="text-2xl font-bold text-white mb-3">
                    Access Denied
                </h1>
                <p className="text-slate-400 text-sm leading-relaxed mb-8">
                    You don&apos;t have permission to view this page.
                    This area is restricted to authorized roles only.
                    {orgUser && (
                        <span className="block mt-2">
                            Your current role is{' '}
                            <span className="font-semibold text-red-400 uppercase">
                                {orgUser.role}
                            </span>
                            .
                        </span>
                    )}
                </p>

                {/* Actions */}
                <div className="flex flex-col sm:flex-row gap-3 justify-center">
                    <Link
                        href={homeHref}
                        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        Go to my Dashboard
                    </Link>
                    <Link
                        href="/auth/login"
                        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/[0.06] hover:bg-white/[0.10] text-slate-300 text-sm font-medium transition-colors border border-white/[0.08]"
                    >
                        Sign in as Different User
                    </Link>
                </div>
            </div>
        </div>
    );
}
