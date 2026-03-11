'use client';

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import { BarChart3, Activity, GitBranch, Users, LogOut, ChevronRight, Shield, Clock } from 'lucide-react';
import { useAuth } from '@/components/AuthProvider';

const navItems = [
    { href: '/dashboard/analyze',   icon: Activity,   label: 'Analyse' },
    { href: '/dashboard/cases',     icon: Clock,      label: 'Case History' },
    { href: '/dashboard/analytics', icon: BarChart3,  label: 'Analytics' },
    { href: '/dashboard/branches',  icon: GitBranch,  label: 'Branches', adminOnly: true },
    { href: '/dashboard/users',     icon: Users,      label: 'Users', adminOnly: true },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const { orgUser, org, loading, signOut } = useAuth();
    const router = useRouter();
    const pathname = usePathname();

    useEffect(() => {
        if (!loading && !orgUser) router.push('/auth/login');
    }, [loading, orgUser, router]);

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <div className="animate-spin w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full" />
                    <p className="text-sm text-slate-500">Loading workspace…</p>
                </div>
            </div>
        );
    }

    if (!orgUser) return null;

    const isAdmin = orgUser.role === 'admin';

    return (
        <div className="min-h-screen flex">
            {/* ── Sidebar ── */}
            <aside className="w-60 shrink-0 flex flex-col border-r border-white/[0.06] bg-[#0d1117]/60 backdrop-blur-xl fixed h-screen z-40">
                {/* Logo */}
                <div className="px-5 py-5 border-b border-white/[0.06]">
                    <Link href="/dashboard/analyze" className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shrink-0">
                            <BarChart3 className="w-4 h-4 text-white" />
                        </div>
                        <span className="font-bold text-white text-sm leading-tight">Integronix</span>
                    </Link>
                    {org && (
                        <div className="mt-3 px-2 py-2 rounded-lg bg-white/[0.04] border border-white/[0.06]">
                            <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold mb-0.5">Organisation</p>
                            <p className="text-xs font-medium text-slate-200 truncate">{org.name}</p>
                        </div>
                    )}
                </div>

                {/* Nav */}
                <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
                    {navItems.map(item => {
                        if (item.adminOnly && !isAdmin) return null;
                        const active = pathname === item.href || pathname.startsWith(item.href + '/');
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group ${active
                                        ? 'bg-indigo-500/20 text-white border border-indigo-500/30'
                                        : 'text-slate-400 hover:text-white hover:bg-white/[0.06]'
                                    }`}
                            >
                                <item.icon className={`w-4 h-4 shrink-0 ${active ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-300'}`} />
                                {item.label}
                                {active && <ChevronRight className="w-3 h-3 ml-auto text-indigo-400/60" />}
                            </Link>
                        );
                    })}
                </nav>

                {/* User footer */}
                <div className="px-3 py-4 border-t border-white/[0.06]">
                    <div className="flex items-center gap-3 px-3 py-3 rounded-xl bg-white/[0.04] mb-2">
                        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
                            {orgUser.full_name.charAt(0).toUpperCase()}
                        </div>
                        <div className="min-w-0 flex-1">
                            <p className="text-xs font-medium text-white truncate">{orgUser.full_name}</p>
                            <div className={`text-[10px] font-semibold uppercase tracking-wider mt-0.5 ${orgUser.role === 'admin' ? 'text-amber-400' : orgUser.role === 'auditor' ? 'text-blue-400' : 'text-emerald-400'
                                }`}>
                                {orgUser.role}
                            </div>
                        </div>
                        <Shield className="w-3.5 h-3.5 text-slate-600 shrink-0" />
                    </div>
                    <button
                        onClick={signOut}
                        className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-sm text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                    >
                        <LogOut className="w-4 h-4" />
                        Sign Out
                    </button>
                </div>
            </aside>

            {/* ── Main content ── */}
            <main className="flex-1 ml-60 min-h-screen overflow-x-hidden">
                {children}
            </main>
        </div>
    );
}
