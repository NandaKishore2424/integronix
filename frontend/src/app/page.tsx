import Link from 'next/link';
import {
    AlertTriangle,
    ArrowRight,
    ArrowUpRight,
    BrainCircuit,
    Cloud,
    Database,
    FileCheck,
    Layers,
    Lock,
    Phone,
    Scale,
    Search,
    Server,
    ShieldCheck,
    TrendingDown,
} from 'lucide-react';
import { BackgroundBeams } from '@/components/ui/background-beams';
import { BentoGrid, type BentoItem } from '@/components/ui/bento-grid';
import { CountUp, HeroItem, HeroStagger, MotionRoot, Reveal, StaggerItem, StaggerList } from '@/components/landing/motion';
import {
    DEMO_VIDEO_URL,
    FACTS,
    PROFILE,
    RESULTS,
    STAGES,
    type CaseResult,
    type StageKind,
} from '@/content/caseStudy';

/*
 * Public case-study page.
 *
 * Deliberately static: no data fetching, no Supabase, no backend calls. The
 * middleware also skips this route. That way the page loads instantly and
 * keeps working while the API and database are switched off between demos.
 */

const NAV = [
    { href: '#built', label: 'What I built' },
    { href: '#how-it-works', label: 'How it works' },
    { href: '#results', label: 'Results' },
    { href: '#engineering', label: 'Engineering' },
    { href: '#contact', label: 'Contact' },
];

const ENGINEERING = [
    {
        icon: Lock,
        title: 'Atomic claim approval',
        body: 'Adjudication is one Postgres transaction with an optimistic lock. Two simultaneous approvals: one succeeds, the other receives 409 — never a second payment.',
    },
    {
        icon: Scale,
        title: 'Exact money',
        body: 'Decimal arithmetic throughout. Patient share is computed as allowed minus paid, so remittance totals reconcile to the cent.',
    },
    {
        icon: ShieldCheck,
        title: 'Fails closed',
        body: 'A failing stage halts every stage after it, and a run that did not produce a usable code cannot be submitted as a claim.',
    },
    {
        icon: Layers,
        title: 'Tenant isolation',
        body: 'The organisation is derived from the verified token — never from the request — and enforced on every query.',
    },
    {
        icon: FileCheck,
        title: 'Tested without secrets',
        body: 'CI runs the suite with no credentials configured, plus schema-contract tests for the database facts that mocks cannot see.',
    },
    {
        icon: Server,
        title: 'Built to operate',
        body: 'Docker image, liveness and readiness probes, request correlation IDs, startup warm-up, and per-user rate limits on LLM endpoints.',
    },
];

const BUILT: BentoItem[] = [
    {
        title: 'Agentic AI pipeline',
        meta: 'LangGraph',
        status: 'AI integration',
        description:
            'A ten-stage LangGraph state graph with typed shared state and conditional routing. An LLM (Groq, gpt-oss-120b) turns free-text notes into structured diagnoses and procedures, each quoting the sentence it came from. A failed stage halts the graph instead of guessing.',
        icon: <BrainCircuit className="h-4 w-4 text-amber-400" />,
        tags: ['LangGraph', 'LLM integration', 'Structured output', 'Prompt design'],
        colSpan: 2,
        hasPersistentHover: true,
    },
    {
        title: 'Semantic search',
        meta: 'pgvector',
        status: 'AI integration',
        description:
            '384-dimensional sentence embeddings for 45,007 ICD-10-CM codes, stored in pgvector, so similarity and billing metadata come back in one SQL query.',
        icon: <Search className="h-4 w-4 text-orange-400" />,
        tags: ['Embeddings', 'Vector search', 'Retrieval'],
    },
    {
        title: 'Production API',
        meta: 'FastAPI',
        status: 'Backend',
        description:
            'JWT auth, organisation-level tenant isolation, rate limits on the LLM routes, and structured JSON logs with a request ID on every call.',
        icon: <Server className="h-4 w-4 text-sky-400" />,
        tags: ['Python', 'FastAPI', 'Pydantic', 'REST'],
    },
    {
        title: 'Money-safe transactions',
        meta: 'PostgreSQL',
        status: 'Backend',
        description:
            'Claim approval is one Postgres function with an optimistic lock: two simultaneous approvals give one success and one 409, never a double payment. Amounts use exact decimal arithmetic end to end.',
        icon: <Database className="h-4 w-4 text-emerald-400" />,
        tags: ['SQL functions', 'Concurrency', 'Transactions', 'Decimal money'],
        colSpan: 2,
    },
    {
        title: 'Security by default',
        meta: 'Supabase',
        status: 'Backend',
        description:
            'Row-level security with deny-by-default grants, least-privilege keys, and secrets that exist only on the server.',
        icon: <ShieldCheck className="h-4 w-4 text-rose-400" />,
        tags: ['RLS', 'Auth', 'Least privilege'],
    },
    {
        title: 'Shipped and operated',
        meta: 'CI/CD',
        status: 'DevOps',
        description:
            'GitHub Actions runs 359 tests, builds and smoke-tests a Docker image, and publishes it. An EC2 server pulls it at boot behind nginx with Let\u2019s Encrypt HTTPS; the frontend ships on Vercel.',
        icon: <Cloud className="h-4 w-4 text-indigo-400" />,
        tags: ['Docker', 'GitHub Actions', 'AWS EC2', 'nginx', 'Vercel'],
        colSpan: 2,
    },
];

const DECISIONS = [
    ['Who picks the billed code', 'Deterministic scoring', 'LLM judgment', 'Reproducible, and defensible in a payer dispute'],
    ['Orchestration', 'LangGraph state graph', 'A hand-written chain', 'Explicit stages, typed shared state, conditional routing'],
    ['Vector search', 'pgvector inside Postgres', 'A separate vector database', 'Similarity and billing metadata in one query'],
    ['Concurrent approvals', 'Optimistic lock in SQL', 'An application-level check', 'The losing request gets 409 instead of a second payment'],
];

const STAGE_STYLE: Record<StageKind, string> = {
    code: 'border-white/[0.07] bg-white/[0.02]',
    llm: 'border-amber-500/40 bg-amber-500/[0.08]',
    decision: 'border-indigo-400/40 bg-indigo-500/[0.10]',
};

export default function CaseStudyPage() {
    const groups = Array.from(new Set(RESULTS.map((r) => r.group)));

    return (
        <MotionRoot>
        <div className="min-h-screen bg-[#0d1117] text-slate-200">
            <SiteNav />

            <main>
                <Hero />

                <Section
                    id="problem"
                    eyebrow="The problem"
                    title="Every claim starts as a clinical note."
                    intro="Medical coding is the step between what a clinician writes and what a hospital is paid. Someone has to translate prose into standardised codes — at volume, under time pressure, from notes never written with billing in mind."
                >
                    <div className="grid gap-4 md:grid-cols-3">
                        <ProblemCard
                            icon={TrendingDown}
                            tone="text-sky-400"
                            title="Undercoding"
                            body="A documented complication is missed, the claim lands in a lower reimbursement tier, and the hospital loses revenue it earned."
                        />
                        <ProblemCard
                            icon={AlertTriangle}
                            tone="text-red-400"
                            title="Overcoding"
                            body="A code claims more than the chart supports. At scale that is billing fraud — the exposure compliance teams exist to prevent."
                        />
                        <ProblemCard
                            icon={Scale}
                            tone="text-amber-400"
                            title="A second opinion"
                            body="Integronix derives the codes independently, shows the evidence behind each one, and flags where a human coder's choice diverges."
                        />
                    </div>
                </Section>

                <Section
                    id="built"
                    eyebrow="What I built"
                    title="Backend engineering and applied AI, end to end."
                    intro="I designed and built every layer myself: the AI pipeline, the API and database, the security model, the tests, and the deployment. These are the skills the project was built to exercise."
                >
                    <BentoGrid items={BUILT} />
                </Section>

                <Section
                    id="how-it-works"
                    eyebrow="How it works"
                    title="A ten-stage pipeline. One stage uses a language model."
                >
                    <div className="glass-card p-6 sm:p-8 mb-10 border-amber-500/20">
                        <p className="text-lg font-semibold text-white mb-3">The LLM never picks the billing code.</p>
                        <p className="text-slate-400 leading-relaxed max-w-4xl">
                            The model is confined to one job: structuring the note into diagnoses and procedures, each quoting
                            the sentence that supports it. Every step after that is deterministic. A scoring function weighs how
                            well the terminology matches, how much specificity the chart actually supports, consistency with the
                            evidence, and whether the chart rules the condition out. When a payer disputes a claim, the answer is
                            a rule and a sentence — not &ldquo;the model was confident.&rdquo;
                        </p>
                    </div>

                    <StaggerList className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                        {STAGES.map((stage, index) => (
                            <StaggerItem
                                key={stage.name}
                                className={`rounded-xl border p-4 transition-colors hover:border-amber-500/40 ${STAGE_STYLE[stage.kind]}`}
                            >
                                <div className="flex items-center justify-between mb-2">
                                    <span className="font-mono text-xs text-slate-500">{String(index + 1).padStart(2, '0')}</span>
                                    {stage.kind === 'llm' && <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-400">LLM</span>}
                                    {stage.kind === 'decision' && <span className="text-[10px] font-semibold uppercase tracking-wider text-indigo-300">Decision</span>}
                                </div>
                                <p className="text-sm font-semibold text-white mb-1">{stage.name}</p>
                                <p className="text-xs text-slate-400 leading-relaxed">{stage.detail}</p>
                            </StaggerItem>
                        ))}
                    </StaggerList>
                </Section>

                <Section
                    id="results"
                    eyebrow="Real results"
                    title="Output from the running system."
                    intro="Captured on 5 September 2026 from synthetic clinical notes, and saved as data, so nothing on this page calls the backend. Scores are the pipeline's composite ranking score, not a calibrated probability."
                >
                    <div className="space-y-12">
                        {groups.map((group) => (
                            <div key={group}>
                                <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-slate-400 mb-4">{group}</h3>
                                <div className="space-y-6">
                                    {RESULTS.filter((r) => r.group === group).map((result) => (
                                        <Reveal key={result.id}>
                                            <ResultCard result={result} />
                                        </Reveal>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </Section>

                <Section
                    id="engineering"
                    eyebrow="Engineering"
                    title="Correctness where it costs money."
                    intro="The parts a billing system cannot get wrong: concurrency, arithmetic, failure handling and tenant boundaries."
                >
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 mb-12">
                        {ENGINEERING.map((item, index) => (
                            <Reveal key={item.title} delay={(index % 3) * 0.08} className="h-full">
                                <div className="glass-card h-full p-6 transition-transform duration-300 hover:-translate-y-1">
                                    <item.icon className="w-5 h-5 text-amber-400 mb-4" />
                                    <p className="font-semibold text-white mb-2">{item.title}</p>
                                    <p className="text-sm text-slate-400 leading-relaxed">{item.body}</p>
                                </div>
                            </Reveal>
                        ))}
                    </div>

                    <h3 className="text-lg font-semibold text-white mb-4">Key decisions</h3>
                    <div className="overflow-x-auto rounded-xl border border-white/[0.07]">
                        <table className="w-full min-w-[640px] text-sm">
                            <thead className="bg-white/[0.03] text-left text-xs uppercase tracking-wider text-slate-500">
                                <tr>
                                    <th className="px-4 py-3 font-medium">Decision</th>
                                    <th className="px-4 py-3 font-medium">Chose</th>
                                    <th className="px-4 py-3 font-medium">Over</th>
                                    <th className="px-4 py-3 font-medium">Because</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/[0.05]">
                                {DECISIONS.map(([decision, chose, over, because]) => (
                                    <tr key={decision}>
                                        <td className="px-4 py-3 text-slate-300">{decision}</td>
                                        <td className="px-4 py-3 font-medium text-white">{chose}</td>
                                        <td className="px-4 py-3 text-slate-500">{over}</td>
                                        <td className="px-4 py-3 text-slate-400">{because}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </Section>

                {DEMO_VIDEO_URL && (
                    <Section id="walkthrough" eyebrow="Walkthrough" title="See the full workflow on video.">
                        <a
                            href={DEMO_VIDEO_URL}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn-primary inline-flex items-center gap-2"
                        >
                            Watch the recorded walkthrough <ArrowUpRight className="w-4 h-4" />
                        </a>
                    </Section>
                )}

                <Contact />
            </main>

            <SiteFooter />
        </div>
        </MotionRoot>
    );
}

function SiteNav() {
    return (
        <nav className="sticky top-0 z-50 border-b border-white/[0.06] bg-[#0d1117]/85 backdrop-blur-xl">
            <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between gap-6">
                <Link href="/" className="flex items-center gap-2.5">
                    <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center text-sm font-black text-white">
                        I
                    </span>
                    <span className="text-lg font-bold text-white tracking-tight">Integronix</span>
                </Link>
                <div className="hidden md:flex items-center gap-7 text-sm text-slate-400">
                    {NAV.map((item) => (
                        <a key={item.href} href={item.href} className="hover:text-white transition-colors">
                            {item.label}
                        </a>
                    ))}
                </div>
                <div className="flex items-center gap-4">
                    <a
                        href={PROFILE.portfolio}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hidden lg:inline-flex items-center gap-1 text-sm text-slate-400 hover:text-white transition-colors"
                    >
                        Portfolio <ArrowUpRight className="w-3.5 h-3.5" />
                    </a>
                    <a
                        href={PROFILE.github}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hidden sm:inline-flex items-center gap-1 text-sm text-slate-400 hover:text-white transition-colors"
                    >
                        GitHub <ArrowUpRight className="w-3.5 h-3.5" />
                    </a>
                    <a href="#contact" className="btn-primary text-sm py-2 px-4">
                        Request a demo
                    </a>
                </div>
            </div>
        </nav>
    );
}

function Hero() {
    return (
        <section className="relative overflow-hidden px-6 pt-24 pb-20">
            <BackgroundBeams className="opacity-70" />
            <div className="pointer-events-none absolute left-1/2 top-10 h-[380px] w-[680px] -translate-x-1/2 rounded-full bg-amber-500/10 blur-[120px]" />
            <HeroStagger className="relative max-w-4xl mx-auto text-center">
                <HeroItem>
                    <a
                        href={PROFILE.portfolio}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-4 py-1.5 text-xs font-medium text-slate-300 mb-6 hover:border-amber-500/40 hover:text-white transition-colors"
                    >
                        <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
                        Designed and built by {PROFILE.name} · Backend &amp; applied AI
                        <ArrowUpRight className="w-3 h-3" />
                    </a>
                </HeroItem>
                <HeroItem>
                    <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight leading-[1.08] text-white mb-6">
                        Clinical coding that{' '}
                        <span className="bg-gradient-to-r from-amber-400 via-orange-500 to-amber-300 bg-[length:200%_auto] bg-clip-text text-transparent animate-gradient-x">
                            shows its work.
                        </span>
                    </h1>
                </HeroItem>
                <HeroItem>
                    <p className="text-lg text-slate-400 leading-relaxed max-w-3xl mx-auto mb-10">
                        Integronix reads a discharge summary, derives ICD-10-CM and CPT codes through a ten-stage agentic
                        pipeline, and audits them against what a human coder billed. A language model structures the note — but
                        the billing code itself is chosen by deterministic rules, so every decision traces back to a sentence in
                        the chart.
                    </p>
                </HeroItem>
                <HeroItem className="flex flex-col sm:flex-row items-center justify-center gap-3">
                    <a href="#results" className="btn-primary inline-flex items-center gap-2 py-3 px-7">
                        See real results <ArrowRight className="w-4 h-4" />
                    </a>
                    <a
                        href={PROFILE.github}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-[#0d1117]/60 px-7 py-3 text-sm font-medium text-slate-300 backdrop-blur hover:border-white/25 hover:text-white transition-colors"
                    >
                        Source on GitHub <ArrowUpRight className="w-4 h-4" />
                    </a>
                </HeroItem>

                <HeroItem>
                    <dl className="mt-14 grid grid-cols-2 gap-6 sm:grid-cols-4">
                        {FACTS.map((fact) => (
                            <div key={fact.label}>
                                <dt className="sr-only">{fact.label}</dt>
                                <dd className="text-3xl font-extrabold text-white tabular-nums">
                                    <CountUp value={fact.value} />
                                </dd>
                                <dd className="mt-1 text-xs font-medium uppercase tracking-widest text-slate-500">{fact.label}</dd>
                            </div>
                        ))}
                    </dl>
                </HeroItem>

                <HeroItem>
                    <p className="mt-12 text-xs text-slate-500">
                        Runs on synthetic clinical notes. It is built to explore a real problem, not to process real patient data.
                    </p>
                </HeroItem>
            </HeroStagger>
        </section>
    );
}

function Section({
    id,
    eyebrow,
    title,
    intro,
    children,
}: {
    id: string;
    eyebrow: string;
    title: string;
    intro?: string;
    children: React.ReactNode;
}) {
    return (
        <section id={id} className="scroll-mt-20 border-t border-white/[0.05] px-6 py-20">
            <div className="max-w-6xl mx-auto">
                <Reveal>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-400 mb-3">{eyebrow}</p>
                    <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white mb-4">{title}</h2>
                    {intro ? <p className="max-w-3xl text-slate-400 leading-relaxed mb-12">{intro}</p> : <div className="mb-10" />}
                </Reveal>
                {children}
            </div>
        </section>
    );
}

function ProblemCard({
    icon: Icon,
    tone,
    title,
    body,
}: {
    icon: typeof Scale;
    tone: string;
    title: string;
    body: string;
}) {
    return (
        <div className="glass-card h-full p-6 transition-transform duration-300 hover:-translate-y-1">
            <Icon className={`w-5 h-5 mb-4 ${tone}`} />
            <p className="font-semibold text-white mb-2">{title}</p>
            <p className="text-sm text-slate-400 leading-relaxed">{body}</p>
        </div>
    );
}

function ResultCard({ result }: { result: CaseResult }) {
    return (
        <article className="glass-card p-6 sm:p-8">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
                <h4 className="text-lg font-semibold text-white">{result.title}</h4>
                <span className="rounded-full border border-white/10 px-3 py-1 text-xs font-medium text-slate-400">
                    Resolved by {result.resolvedBy}
                </span>
            </div>

            <div className="grid gap-8 lg:grid-cols-2">
                <div>
                    <p className="mono-label mb-3">From the note</p>
                    <div className="space-y-2 rounded-xl border border-white/[0.07] bg-black/30 p-4 font-mono text-[13px] leading-relaxed text-slate-300">
                        {result.noteExcerpt.map((line) => (
                            <p key={line}>{line}</p>
                        ))}
                    </div>
                    <p className="mt-4 text-sm text-slate-400 leading-relaxed">{result.lesson}</p>
                    {result.footnote && <p className="mt-3 text-xs text-slate-500 leading-relaxed">{result.footnote}</p>}
                </div>

                <div>
                    <p className="mono-label mb-3">Selected code</p>
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-1">
                        <span className="font-mono text-3xl font-bold text-white">{result.code}</span>
                        <span className="text-sm font-medium text-emerald-400 tabular-nums">score {result.score.toFixed(2)}</span>
                    </div>
                    <p className="text-slate-300 mb-6">{result.description}</p>

                    <p className="mono-label mb-3">Candidates considered</p>
                    <ul className="space-y-3 mb-6">
                        {result.candidates.map((candidate, index) => (
                            <li key={candidate.code}>
                                <div className="flex items-baseline justify-between gap-3 text-sm">
                                    <span className="min-w-0">
                                        <span className="font-mono text-slate-200">{candidate.code}</span>{' '}
                                        <span className="text-slate-500">{candidate.description}</span>
                                    </span>
                                    <span className="shrink-0 font-mono text-slate-400 tabular-nums">{candidate.score.toFixed(3)}</span>
                                </div>
                                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-white/[0.06]" aria-hidden="true">
                                    <div
                                        className={`h-full rounded-full ${index === 0 ? 'bg-amber-400' : 'bg-slate-600'}`}
                                        style={{ width: `${Math.round(candidate.score * 100)}%` }}
                                    />
                                </div>
                            </li>
                        ))}
                    </ul>

                    <p className="mono-label mb-2">Evidence the extractor anchored to</p>
                    <blockquote className="border-l-2 border-amber-500/60 pl-3 text-sm italic text-slate-300">
                        &ldquo;{result.evidence}&rdquo;
                    </blockquote>

                    {result.procedure && (
                        <div className="mt-6 flex items-center justify-between gap-4 rounded-xl border border-white/[0.07] bg-white/[0.02] px-4 py-3 text-sm">
                            <span className="min-w-0">
                                <span className="font-mono text-slate-200">CPT {result.procedure.code}</span>{' '}
                                <span className="text-slate-500">{result.procedure.description}</span>
                            </span>
                            <span className="shrink-0 font-mono font-semibold text-amber-400">{result.procedure.charge}</span>
                        </div>
                    )}
                </div>
            </div>
        </article>
    );
}

function Contact() {
    return (
        <section id="contact" className="scroll-mt-20 border-t border-white/[0.05] px-6 py-24">
            <div className="max-w-3xl mx-auto text-center">
                <Reveal>
                <div className="glass-card mb-16 p-6 sm:p-8 text-left">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-400 mb-3">Why I built this</p>
                    <p className="text-slate-300 leading-relaxed mb-4">
                        Coding errors cost hospitals revenue they earned, and overcoding exposes them to fraud findings. I wanted
                        to see how far careful engineering could take this problem: let a language model do what it is good at,
                        reading messy clinical prose, and keep every billing decision deterministic, explainable and testable.
                    </p>
                    <p className="text-slate-400 leading-relaxed mb-6">
                        Building it end to end also let me deepen the skills I enjoy most: backend systems that handle money
                        correctly, practical AI integration, and running software in production.
                    </p>
                    <a
                        href={PROFILE.portfolio}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 text-sm font-medium text-amber-400 hover:text-amber-300 transition-colors"
                    >
                        Like this project? See more of my work <ArrowUpRight className="w-4 h-4" />
                    </a>
                </div>
                </Reveal>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-400 mb-3">See it running</p>
                <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white mb-6">
                    I&rsquo;d be glad to walk you through a live demo.
                </h2>
                <p className="text-slate-400 leading-relaxed mb-4">
                    The live system runs on a paid LLM API and a hosted database, so rather than leaving it open to the
                    public, I demo it personally — the coding pipeline, the payer workflow, and any part of the design
                    you&rsquo;d like to explore in more depth.
                </p>
                <p className="text-slate-400 leading-relaxed mb-10">
                    Please feel free to reach out on LinkedIn or by phone, and I&rsquo;ll get back to you as soon as I can.
                </p>
                <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                    <a
                        href={PROFILE.linkedin}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn-primary inline-flex items-center gap-2 py-3 px-7"
                    >
                        Connect on LinkedIn <ArrowUpRight className="w-4 h-4" />
                    </a>
                    <a
                        href={PROFILE.phoneHref}
                        className="inline-flex items-center gap-2 rounded-xl border border-white/10 px-7 py-3 text-sm font-medium text-slate-300 hover:border-white/25 hover:text-white transition-colors"
                    >
                        <Phone className="w-4 h-4" /> {PROFILE.phoneDisplay}
                    </a>
                </div>
                <div className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-slate-500">
                    <a
                        href={PROFILE.portfolio}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 hover:text-slate-300 transition-colors"
                    >
                        My portfolio <ArrowUpRight className="w-3.5 h-3.5" />
                    </a>
                    <a
                        href={PROFILE.github}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 hover:text-slate-300 transition-colors"
                    >
                        Source on GitHub <ArrowUpRight className="w-3.5 h-3.5" />
                    </a>
                </div>
            </div>
        </section>
    );
}

function SiteFooter() {
    return (
        <footer className="border-t border-white/[0.06] px-6 py-8">
            <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-slate-500">
                <p>© 2026 {PROFILE.name} · Built with synthetic clinical data</p>
                <div className="flex items-center gap-6">
                    <a href={PROFILE.portfolio} target="_blank" rel="noopener noreferrer" className="hover:text-slate-300 transition-colors">
                        Portfolio
                    </a>
                    <a href={PROFILE.github} target="_blank" rel="noopener noreferrer" className="hover:text-slate-300 transition-colors">
                        GitHub
                    </a>
                    <Link href="/auth/login" className="hover:text-slate-300 transition-colors">
                        Staff sign-in
                    </Link>
                </div>
            </div>
        </footer>
    );
}
