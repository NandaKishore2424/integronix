'use client';

import { useState, useRef, useCallback } from 'react';
import { Send, Loader2, AlertCircle, FileText, Hash, BookOpen, Upload, X, FileCheck2, ScanText } from 'lucide-react';

interface Props {
    onSubmit: (text: string, humanCode: string) => void;
    onSubmitPdf: (file: File, humanCode: string) => void;
    loading: boolean;
    stageLabel: string;
    error: string | null;
}

const SAMPLE_CASES = [
    {
        label: 'Diabetes + CKD',
        text: 'Patient has Type 2 diabetes mellitus with chronic kidney disease stage 3. eGFR is 42 mL/min. Blood pressure controlled with lisinopril.',
        code: 'E11.9',
    },
    {
        label: 'Low Back Pain',
        text: 'Patient reports chronic low back pain for 6 months, radiating to the left leg. Pain score 7/10. No prior surgery.',
        code: '',
    },
    {
        label: 'Uncomplicated Diabetes',
        text: 'Patient has diabetes. No complications documented. Blood glucose slightly elevated. No kidney disease noted.',
        code: '',
    },
];

const MAX_PDF_BYTES = 20 * 1024 * 1024; // 20 MB

export default function CodeInputPanel({ onSubmit, onSubmitPdf, loading, stageLabel, error }: Props) {
    const [mode, setMode] = useState<'text' | 'pdf'>('text');
    const [text, setText] = useState('');
    const [humanCode, setHumanCode] = useState('');
    const [pdfFile, setPdfFile] = useState<File | null>(null);
    const [isDragging, setIsDragging] = useState(false);
    const [fileError, setFileError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // ── Text submit ────────────────────────────────────────────────────────
    function handleTextSubmit(e: React.FormEvent) {
        e.preventDefault();
        if (!text.trim() || text.trim().length < 20) return;
        onSubmit(text, humanCode);
    }

    // ── PDF submit ─────────────────────────────────────────────────────────
    function handlePdfSubmit(e: React.FormEvent) {
        e.preventDefault();
        if (!pdfFile) return;
        onSubmitPdf(pdfFile, humanCode);
    }

    function loadSample(s: typeof SAMPLE_CASES[0]) {
        setMode('text');
        setText(s.text);
        setHumanCode(s.code);
    }

    // ── File validation & selection ────────────────────────────────────────
    const validateAndSetFile = useCallback((file: File | null) => {
        setFileError(null);
        if (!file) return;
        if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
            setFileError('Only PDF files are accepted.');
            return;
        }
        if (file.size > MAX_PDF_BYTES) {
            setFileError(`File is too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum is 20 MB.`);
            return;
        }
        if (file.size === 0) {
            setFileError('The selected file is empty.');
            return;
        }
        setPdfFile(file);
    }, []);

    // ── Drag & drop handlers ───────────────────────────────────────────────
    function onDragOver(e: React.DragEvent) { e.preventDefault(); setIsDragging(true); }
    function onDragLeave() { setIsDragging(false); }
    function onDrop(e: React.DragEvent) {
        e.preventDefault();
        setIsDragging(false);
        validateAndSetFile(e.dataTransfer.files[0] ?? null);
    }

    function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
        validateAndSetFile(e.target.files?.[0] ?? null);
        e.target.value = ''; // reset so same file can be re-selected
    }

    const charCount = text.trim().length;
    const canSubmitText = charCount >= 20 && !loading;
    const canSubmitPdf = !!pdfFile && !loading;

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fade-in">

            {/* ── Main input ── */}
            <div className="lg:col-span-2 glass-card p-6">

                {/* Mode tabs */}
                <div className="flex gap-1 p-1 rounded-xl bg-white/[0.04] border border-white/[0.06] mb-5 w-fit">
                    {(['text', 'pdf'] as const).map((m) => (
                        <button
                            key={m}
                            type="button"
                            onClick={() => { setMode(m); setFileError(null); }}
                            disabled={loading}
                            className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-semibold transition-all duration-150 ${
                                mode === m
                                    ? 'bg-indigo-600 text-white shadow-sm'
                                    : 'text-slate-400 hover:text-slate-200'
                            }`}
                        >
                            {m === 'text'
                                ? <><FileText className="w-3.5 h-3.5" /> Paste Text</>
                                : <><Upload className="w-3.5 h-3.5" /> Upload PDF</>}
                        </button>
                    ))}
                </div>

                <form onSubmit={mode === 'text' ? handleTextSubmit : handlePdfSubmit} className="flex flex-col gap-5 h-full">

                    {/* ── Text mode ── */}
                    {mode === 'text' && (
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <label className="flex items-center gap-2 text-sm font-semibold text-slate-200">
                                    <FileText className="w-4 h-4 text-indigo-400" />
                                    Clinical Documentation
                                </label>
                                <span className={`text-xs font-mono ${charCount >= 20 ? 'text-slate-500' : 'text-amber-400'}`}>
                                    {charCount} chars {charCount < 20 ? `(need ${20 - charCount} more)` : ''}
                                </span>
                            </div>
                            <textarea
                                className="clinical-textarea"
                                rows={9}
                                placeholder={`Paste discharge summary, progress notes, or SOAP documentation here…\n\nExample:\n"Patient has Type 2 diabetes mellitus with chronic kidney disease stage 3. eGFR is 42 mL/min."`}
                                value={text}
                                onChange={e => setText(e.target.value)}
                                disabled={loading}
                            />
                        </div>
                    )}

                    {/* ── PDF mode ── */}
                    {mode === 'pdf' && (
                        <div>
                            <label className="flex items-center gap-2 text-sm font-semibold text-slate-200 mb-2">
                                <ScanText className="w-4 h-4 text-indigo-400" />
                                Discharge Summary PDF
                                <span className="text-xs font-normal text-slate-500 ml-1">Max 20 MB · Digital or scanned</span>
                            </label>

                            {/* Drag-drop zone */}
                            {!pdfFile ? (
                                <div
                                    onDragOver={onDragOver}
                                    onDragLeave={onDragLeave}
                                    onDrop={onDrop}
                                    onClick={() => fileInputRef.current?.click()}
                                    className={`flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed cursor-pointer transition-all duration-200 min-h-[180px]
                                        ${isDragging
                                            ? 'border-indigo-500 bg-indigo-500/10'
                                            : 'border-white/[0.12] hover:border-indigo-500/50 hover:bg-white/[0.03]'
                                        }`}
                                >
                                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center transition-colors duration-200
                                        ${isDragging ? 'bg-indigo-500/20' : 'bg-white/[0.06]'}`}>
                                        <Upload className={`w-6 h-6 ${isDragging ? 'text-indigo-400' : 'text-slate-500'}`} />
                                    </div>
                                    <div className="text-center">
                                        <p className="text-sm font-semibold text-slate-300">
                                            {isDragging ? 'Drop it here' : 'Drop discharge summary PDF'}
                                        </p>
                                        <p className="text-xs text-slate-500 mt-1">
                                            or <span className="text-indigo-400 underline underline-offset-2">click to browse</span>
                                        </p>
                                    </div>
                                    <p className="text-[11px] text-slate-600">
                                        Digital PDFs and scanned documents supported
                                    </p>
                                    <input
                                        ref={fileInputRef}
                                        type="file"
                                        accept=".pdf,application/pdf"
                                        className="hidden"
                                        onChange={onFileChange}
                                        disabled={loading}
                                    />
                                </div>
                            ) : (
                                /* File selected — show info card */
                                <div className="flex items-center gap-4 rounded-xl border border-emerald-500/25 bg-emerald-500/5 px-5 py-4">
                                    <div className="w-10 h-10 rounded-xl bg-emerald-500/15 flex items-center justify-center shrink-0">
                                        <FileCheck2 className="w-5 h-5 text-emerald-400" />
                                    </div>
                                    <div className="min-w-0 flex-1">
                                        <p className="text-sm font-semibold text-white truncate">{pdfFile.name}</p>
                                        <p className="text-xs text-slate-400 mt-0.5">
                                            {(pdfFile.size / 1024).toFixed(0)} KB · PDF document
                                        </p>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => { setPdfFile(null); setFileError(null); }}
                                        className="shrink-0 p-1.5 rounded-lg text-slate-500 hover:text-white hover:bg-white/[0.08] transition-colors"
                                        title="Remove file"
                                        disabled={loading}
                                    >
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>
                            )}

                            {/* File error */}
                            {fileError && (
                                <div className="flex items-start gap-3 rounded-xl border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm text-red-400 mt-3 animate-fade-in">
                                    <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                                    <span>{fileError}</span>
                                </div>
                            )}
                        </div>
                    )}

                    {/* ── Existing ICD code (shared between both modes) ── */}
                    <div>
                        <label className="flex items-center gap-2 text-sm font-semibold text-slate-200 mb-2">
                            <Hash className="w-4 h-4 text-slate-400" />
                            Existing Code for Review
                            <span className="text-xs font-normal text-slate-500 ml-1">(optional — enables compliance comparison)</span>
                        </label>
                        <input
                            type="text"
                            className="clinical-textarea font-mono uppercase"
                            style={{ height: '44px', resize: 'none' }}
                            placeholder="e.g. E11.9"
                            value={humanCode}
                            onChange={e => setHumanCode(e.target.value.toUpperCase())}
                            disabled={loading}
                            maxLength={10}
                        />
                    </div>

                    {/* ── Pipeline error ── */}
                    {error && (
                        <div className="flex items-start gap-3 rounded-xl border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm text-red-400 animate-fade-in">
                            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                            <span>{error}</span>
                        </div>
                    )}

                    {/* ── Submit bar ── */}
                    <div className="flex items-center justify-between pt-1">
                        {loading ? (
                            <div className="flex items-center gap-3 text-sm text-slate-400 animate-fade-in">
                                <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
                                <span className="text-indigo-400 font-medium">{stageLabel}</span>
                            </div>
                        ) : (
                            <span className="text-xs text-slate-600">
                                {mode === 'pdf'
                                    ? 'Supports digital PDFs and scanned documents (OCR)'
                                    : 'Validates against ICD-10-CM 2024 · FHIR R4 output'}
                            </span>
                        )}
                        <button
                            type="submit"
                            className="btn-primary flex items-center gap-2"
                            disabled={mode === 'text' ? !canSubmitText : !canSubmitPdf}
                        >
                            {loading
                                ? <><Loader2 className="w-4 h-4 animate-spin" /> Analysing…</>
                                : <><Send className="w-4 h-4" /> Analyse Documentation</>}
                        </button>
                    </div>
                </form>
            </div>

            {/* ── Sidebar ── */}
            <div className="flex flex-col gap-4">

                {/* Sample cases — only relevant in text mode */}
                <div className="glass-card p-5">
                    <div className="section-header">
                        <BookOpen className="w-3 h-3" />
                        Sample Cases
                    </div>
                    <div className="flex flex-col gap-2">
                        {SAMPLE_CASES.map(s => (
                            <button
                                key={s.label}
                                onClick={() => loadSample(s)}
                                disabled={loading}
                                className="text-left p-3 rounded-lg border border-white/[0.06] hover:border-indigo-500/30 hover:bg-white/[0.04] transition-all duration-150 group"
                            >
                                <p className="text-sm font-semibold text-slate-200 group-hover:text-indigo-300 transition-colors">
                                    {s.label}
                                </p>
                                <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{s.text}</p>
                                {s.code && (
                                    <span className="mt-1.5 inline-block text-xs font-mono text-slate-400 bg-white/[0.04] px-2 py-0.5 rounded">
                                        Current code: {s.code}
                                    </span>
                                )}
                            </button>
                        ))}
                    </div>
                </div>

                {/* How it works */}
                <div className="glass-card p-5">
                    <div className="section-header">How It Works</div>
                    <ol className="flex flex-col gap-2">
                        {[
                            ['1', 'Document Ingestion', 'Text paste or PDF → OCR extraction'],
                            ['2', 'Entity Recognition', 'Diagnoses and conditions extracted'],
                            ['3', 'Terminology Validation', 'Clinical ontology cross-check'],
                            ['4', 'Code Mapping', 'ICD-10-CM crosswalk lookup'],
                            ['5', 'Semantic Fallback', 'Vector similarity matching'],
                            ['6', 'Code Selection', 'Rule-based specificity engine'],
                            ['7', 'Compliance Audit', 'Revenue gap detection'],
                            ['8', 'Risk Assessment', 'Audit probability scoring'],
                        ].map(([n, name, desc]) => (
                            <li key={n} className="flex items-start gap-2.5">
                                <span className="shrink-0 w-5 h-5 rounded-full bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-[10px] font-bold text-indigo-300">
                                    {n}
                                </span>
                                <div>
                                    <p className="text-xs font-semibold text-slate-200">{name}</p>
                                    <p className="text-[11px] text-slate-500">{desc}</p>
                                </div>
                            </li>
                        ))}
                    </ol>
                </div>

            </div>
        </div>
    );
}
