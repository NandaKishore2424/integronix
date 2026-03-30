'use client';

import Link from 'next/link';
import { ArrowRight, Shield, BarChart3, FileCheck, Lock, Users, Globe, CheckCircle, AlertTriangle, TrendingUp } from 'lucide-react';

export default function LandingPage() {
  return (
    <div className="min-h-screen">
      {/* ── Nav ── */}
      <nav className="fixed top-0 w-full z-50 border-b border-white/[0.06] bg-[#0d1117]/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
              <BarChart3 className="w-4 h-4 text-white" />
            </div>
            <span className="text-lg font-bold text-white tracking-tight">CodePerfect Auditor</span>
            <span className="hidden sm:block text-xs font-medium text-slate-500 border border-white/10 rounded-full px-2.5 py-0.5">Revenue Integrity Platform</span>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/auth/login" className="text-sm font-medium text-slate-400 hover:text-white transition-colors px-4 py-2">
              Sign In
            </Link>
            <Link href="/auth/signup" className="btn-primary text-sm py-2.5 px-5 flex items-center gap-2">
              Get Started <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="pt-40 pb-24 px-6 text-center relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 left-1/2 -translate-x-1/2 w-[700px] h-[400px] bg-amber-500/10 blur-[120px] rounded-full" />
        </div>
        <div className="relative max-w-4xl mx-auto">
          <div className="inline-flex items-center gap-2 text-xs font-semibold text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-full px-4 py-1.5 mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            HIPAA-Ready · HL7 FHIR R4 · SOC 2 Type II
          </div>
          <h1 className="text-5xl sm:text-6xl font-extrabold leading-[1.08] mb-6 tracking-tight">
            Stop Losing Revenue to{' '}
            <span className="bg-gradient-to-r from-amber-400 via-orange-400 to-orange-500 bg-clip-text text-transparent">
              Coding Errors
            </span>
          </h1>
          <p className="text-lg text-slate-400 max-w-2xl mx-auto leading-relaxed mb-10">
            CodePerfect Auditor is an AI-powered medical coding audit engine that catches undercoding, overcoding, and specificity gaps — before your claim hits the payer.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/auth/signup" className="btn-primary text-base py-3.5 px-8 flex items-center gap-2">
              Start Free Trial <ArrowRight className="w-4 h-4" />
            </Link>
            <Link href="/auth/login" className="text-sm font-medium text-slate-400 hover:text-white transition-colors flex items-center gap-2 py-3.5 px-6 rounded-xl border border-white/10 hover:border-white/20">
              Sign In to Dashboard
            </Link>
          </div>
          {/* Stats */}
          <div className="flex flex-wrap justify-center gap-8 mt-16">
            {[
              { value: '99.2%', label: 'Coding Accuracy' },
              { value: '$36B', label: 'Industry Loss Annually' },
              { value: '<2s', label: 'Per Case Analysis' },
            ].map(s => (
              <div key={s.value} className="text-center">
                <div className="text-3xl font-extrabold text-white mb-1">{s.value}</div>
                <div className="text-xs text-slate-500 font-medium uppercase tracking-widest">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Problem Section ── */}
      <section className="py-20 px-6 border-t border-white/[0.05]">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-3">The $36 Billion Problem</h2>
            <p className="text-slate-400 max-w-xl mx-auto">Real settlements. Real hospitals. Real consequences of wrong ICD codes.</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { icon: AlertTriangle, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20', amount: '$1.7 Billion', name: 'Columbia/HCA', detail: 'ICD overcoding — exaggerated diagnosis severity to inflate DRG payments' },
              { icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/20', amount: '$900 Million', name: 'Tenet Healthcare', detail: 'Incorrect ICD codes assigned to make patients appear sicker than documented' },
              { icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20', amount: '$1 Billion recouped', name: 'OIG Audit (2020)', detail: '9 of 10 "severe malnutrition" claims rejected — no clinical documentation to support the code' },
            ].map(c => (
              <div key={c.name} className={`glass-card p-6 border ${c.bg}`}>
                <c.icon className={`w-5 h-5 ${c.color} mb-4`} />
                <div className={`text-2xl font-extrabold ${c.color} mb-1`}>{c.amount}</div>
                <div className="text-sm font-semibold text-white mb-2">{c.name}</div>
                <div className="text-xs text-slate-400 leading-relaxed">{c.detail}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How It Works ── */}
      <section className="py-20 px-6 border-t border-white/[0.05]">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold mb-3">How CodePerfect Auditor Works</h2>
            <p className="text-slate-400">Three steps — from messy doctor notes to clean, audit-ready ICD codes.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { step: '01', title: 'Submit Clinical Documentation', desc: 'Paste discharge summaries, clinical notes, or upload PDFs. We handle abbreviations, messy writing, and scanned documents.' },
              { step: '02', title: 'AI Analyses in Under 2 Seconds', desc: '8-node pipeline: entity extraction → SNOMED resolution → ICD crosswalk → deterministic scoring → DRG-aware audit comparison.' },
              { step: '03', title: 'Receive the Full Compliance Report', desc: 'Recommended ICD code, confidence score, financial delta, risk assessment, and full FHIR R4 export — ready for your EHR.' },
            ].map(s => (
              <div key={s.step} className="glass-card p-6 relative">
                <div className="text-5xl font-extrabold text-white/[0.06] absolute top-4 right-5 font-mono">{s.step}</div>
                <div className="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/30 flex items-center justify-center mb-4">
                  <span className="text-xs font-bold text-amber-400">{s.step}</span>
                </div>
                <h3 className="font-semibold text-white mb-2">{s.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="py-20 px-6 border-t border-white/[0.05]">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold mb-3">Built for Healthcare Enterprises</h2>
            <p className="text-slate-400">Not a startup MVP — architected for multi-hospital deployments from day one.</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[
              { icon: Users, title: 'Multi-Tenant Architecture', desc: 'Hospital → Branch → User hierarchy with complete data isolation. City General can never see St. Mary\'s records.' },
              { icon: Shield, title: 'Row-Level Security', desc: 'Supabase RLS enforced at the database level. Even if code has bugs, your data stays separated.' },
              { icon: Lock, title: 'Role-Based Access', desc: 'Admin, Auditor, Coder — each sees only what they need. Branch coders see only their branch\'s cases.' },
              { icon: FileCheck, title: 'FHIR R4 Export', desc: 'Every result is output as an HL7 FHIR R4 Condition resource — ready for direct EHR integration.' },
              { icon: TrendingUp, title: 'Revenue Impact Analysis', desc: 'See the exact dollar difference between your submitted code and the AI recommendation per claim.' },
              { icon: Globe, title: 'Full Audit Trail', desc: 'Every pipeline decision logged. Every node, every LLM call, every fallback — permanently traceable.' },
            ].map(f => (
              <div key={f.title} className="glass-card p-5 group hover:border-amber-500/30 transition-all duration-200">
                <div className="flex items-start gap-4">
                  <div className="w-9 h-9 rounded-lg bg-amber-500/15 flex items-center justify-center shrink-0 group-hover:bg-amber-500/25 transition-colors">
                    <f.icon className="w-4.5 h-4.5 text-amber-400" style={{ width: '18px', height: '18px' }} />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white text-sm mb-1">{f.title}</h3>
                    <p className="text-xs text-slate-400 leading-relaxed">{f.desc}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="py-24 px-6 border-t border-white/[0.05] text-center">
        <div className="max-w-2xl mx-auto">
          <h2 className="text-4xl font-extrabold mb-4">Ready to protect your revenue?</h2>
          <p className="text-slate-400 mb-8">Set up your hospital in under 2 minutes. Free to get started.</p>
          <Link href="/auth/signup" className="btn-primary text-base py-4 px-10 inline-flex items-center gap-2">
            Create Organisation Account <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-white/[0.06] py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
              <BarChart3 className="w-3 h-3 text-white" />
            </div>
            <span className="text-sm font-semibold text-white">CodePerfect Auditor</span>
            <span className="text-slate-600 text-sm">© 2025</span>
          </div>
          <div className="flex items-center gap-3 flex-wrap justify-center">
            {['SOC 2 Type II', 'HIPAA Compliant', 'HL7 FHIR R4', 'ICD-10-CM 2024'].map(b => (
              <span key={b} className="flex items-center gap-1 text-xs font-medium text-slate-500 border border-white/[0.08] rounded-full px-3 py-1">
                <CheckCircle className="w-3 h-3 text-emerald-500" />
                {b}
              </span>
            ))}
          </div>
        </div>
      </footer>
    </div>
  );
}
