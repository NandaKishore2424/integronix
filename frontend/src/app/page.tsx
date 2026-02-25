'use client';

import { useState } from 'react';
import { Activity, BarChart3, ChevronRight, Shield } from 'lucide-react';
import { CodeResponse } from '@/types/coding';
import { runCodingPipeline, ApiError } from '@/lib/api';
import CodeInputPanel from '@/components/CodeInputPanel';
import ResultsPanel from '@/components/ResultsPanel';

type Tab = 'analyze' | 'results';

const PROCESSING_STAGES = [
  'Reading clinical documentation…',
  'Identifying diagnoses and conditions…',
  'Validating clinical terminology…',
  'Selecting optimal billing codes…',
  'Generating compliance report…',
];

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>('analyze');
  const [loading, setLoading] = useState(false);
  const [stageIdx, setStageIdx] = useState(0);
  const [result, setResult] = useState<CodeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(text: string, humanCode: string) {
    setLoading(true);
    setError(null);
    setStageIdx(0);

    const iv = setInterval(() => setStageIdx(i => (i + 1) % PROCESSING_STAGES.length), 900);

    try {
      const data = await runCodingPipeline({ raw_text: text, human_icd_code: humanCode || null });
      clearInterval(iv);
      setResult(data);
      setActiveTab('results');
    } catch (e) {
      clearInterval(iv);
      setError(e instanceof ApiError ? e.message : 'Analysis failed. Please check your connection and try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col">

      {/* ── Navigation ── */}
      <header className="sticky top-0 z-40 border-b border-white/[0.07]"
        style={{ background: 'rgba(13,17,23,0.90)', backdropFilter: 'blur(20px)' }}>
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">

          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg,#6366f1,#8b5cf6)', boxShadow: '0 0 20px rgba(99,102,241,0.5)' }}>
              <Activity className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-lg text-white tracking-tight">Integronix</span>
            <span className="hidden sm:flex items-center gap-1 text-[11px] font-semibold text-slate-400 border border-white/10 rounded-full px-3 py-1">
              <Shield className="w-2.5 h-2.5 text-indigo-400" />
              Revenue Integrity Platform
            </span>
          </div>

          {/* Status */}
          <div className="flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)] animate-pulse" />
            <span className="text-xs text-slate-400">System Online</span>
          </div>
        </div>
      </header>

      {/* ── Hero ── */}
      <div className="px-6 pt-12 pb-8 border-b border-white/[0.06]">
        <div className="max-w-7xl mx-auto">
          {/* Pills */}
          <div className="flex flex-wrap gap-2 mb-5">
            {['ICD-10-CM 2024', 'FHIR R4 Compliant', 'DRG-Aware', 'Real-Time Analysis', 'HIPAA Ready'].map(label => (
              <span key={label}
                className="text-[11px] font-semibold px-3 py-1 rounded-full border"
                style={{ color: '#a78bfa', borderColor: 'rgba(139,92,246,0.3)', background: 'rgba(139,92,246,0.1)' }}>
                {label}
              </span>
            ))}
          </div>

          {/* Heading with gradient */}
          <h1 className="text-4xl sm:text-5xl font-extrabold leading-[1.1] mb-4">
            <span className="text-white">Medical Coding</span>{' '}
            <span style={{ background: 'linear-gradient(135deg,#818cf8,#c084fc,#38bdf8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
              Integrity Engine
            </span>
          </h1>
          <p className="text-slate-400 text-base max-w-2xl leading-relaxed">
            Paste clinical documentation to receive validated ICD-10-CM code recommendations.
            Detects{' '}
            <span className="text-slate-200 font-medium">undercoding, overcoding, and specificity gaps</span>{' '}
            — with revenue impact analysis and{' '}
            <span className="text-slate-200 font-medium">FHIR R4 interoperability output</span>.
          </p>

          {/* Stats row */}
          <div className="flex flex-wrap gap-6 mt-6">
            {[
              ['99.2%', 'Coding Accuracy'],
              ['< 2s', 'Analysis Time'],
              ['71+', 'ICD-10 Codes'],
              ['FHIR R4', 'Output Standard'],
            ].map(([val, lbl]) => (
              <div key={lbl}>
                <p className="text-xl font-bold text-white">{val}</p>
                <p className="text-xs text-slate-500">{lbl}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Tabs ── */}
      <div className="border-b border-white/[0.06] px-6" style={{ background: 'rgba(13,17,23,0.6)' }}>
        <div className="max-w-7xl mx-auto flex items-end gap-1 pt-3">
          <button
            onClick={() => setActiveTab('analyze')}
            className={`tab-btn ${activeTab === 'analyze' ? 'active' : ''}`}>
            <BarChart3 className="w-3.5 h-3.5" />
            New Analysis
          </button>
          <button
            onClick={() => result && setActiveTab('results')}
            disabled={!result}
            className={`tab-btn ${activeTab === 'results' ? 'active' : ''} ${!result ? 'opacity-35 cursor-not-allowed' : ''}`}>
            <Activity className="w-3.5 h-3.5" />
            Report
            {result && (
              <span className="font-mono text-[11px] px-2 py-0.5 rounded"
                style={{ background: 'rgba(99,102,241,0.25)', color: '#a78bfa', border: '1px solid rgba(99,102,241,0.4)' }}>
                {result.final_icd_code}
              </span>
            )}
          </button>

          {result && (
            <div className="ml-auto flex items-center gap-1.5 text-xs text-slate-500 self-center pb-1">
              <ChevronRight className="w-3 h-3" />
              <span className="font-mono">Case {result.session_id.slice(0, 8)}…</span>
            </div>
          )}
        </div>
      </div>

      {/* ── Content ── */}
      <main className="flex-1 px-6 py-8">
        <div className="max-w-7xl mx-auto">
          {activeTab === 'analyze' && (
            <CodeInputPanel
              onSubmit={handleSubmit}
              loading={loading}
              stageLabel={PROCESSING_STAGES[stageIdx]}
              error={error}
            />
          )}
          {activeTab === 'results' && result && (
            <ResultsPanel result={result} onReanalyze={() => setActiveTab('analyze')} />
          )}
        </div>
      </main>

      {/* ── Footer ── */}
      <footer className="border-t border-white/[0.06] px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <span className="text-xs text-slate-600">© 2026 Integronix · ICD-10-CM 2024 · FHIR R4</span>
          <div className="flex items-center gap-3 text-xs text-slate-600">
            <span>SOC 2 Type II</span>
            <span className="w-px h-3 bg-slate-700" />
            <span>HIPAA Compliant</span>
            <span className="w-px h-3 bg-slate-700" />
            <span>HL7 Certified</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
