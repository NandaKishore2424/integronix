/**
 * Content for the public case-study page (app/page.tsx).
 *
 * RESULTS are real pipeline output, captured from the running system on
 * 5 September 2026 (coding_results rows) — not illustrations. They are stored
 * here as data rather than fetched, so the page makes no backend or database
 * calls at all: the link keeps working while the API is switched off between
 * demos.
 */

export const PROFILE = {
    name: 'Nanda Kishore R',
    linkedin: 'https://www.linkedin.com/in/nanda-kishore-7290551b8/',
    phoneDisplay: '+91 93442 48604',
    phoneHref: 'tel:+919344248604',
    github: 'https://github.com/NandaKishore2424/integronix',
    portfolio: 'https://nandakishorer.vercel.app/',
    email: 'r.nandakishore24@gmail.com',
} as const;

/** Link to the recorded walkthrough. The video section renders only once this is set. */
export const DEMO_VIDEO_URL: string = 'https://youtu.be/WPeQFqlHPM0';

/** The same video as a privacy-preserving embed: youtube-nocookie sets no tracking cookie until play. */
export const DEMO_VIDEO_EMBED = 'https://www.youtube-nocookie.com/embed/WPeQFqlHPM0?rel=0';

export const FACTS = [
    { value: 98186, label: 'ICD-10-CM codes' },
    { value: 379283, label: 'SNOMED CT concepts' },
    { value: 10, label: 'pipeline stages' },
    { value: 361, label: 'automated tests' },
] as const;

export type StageKind = 'code' | 'llm' | 'decision';

export const STAGES: { name: string; detail: string; kind: StageKind }[] = [
    { name: 'Document intake', detail: 'Text from PDFs, with OCR for scanned pages', kind: 'code' },
    { name: 'Clinical extraction', detail: 'Prose becomes diagnoses and procedures, each quoting its evidence', kind: 'llm' },
    { name: 'Procedure coding', detail: 'Procedures matched to CPT / HCPCS', kind: 'code' },
    { name: 'Concept resolution', detail: 'Each diagnosis mapped to a SNOMED CT concept', kind: 'code' },
    { name: 'Crosswalk', detail: 'SNOMED CT concept to ICD-10-CM code', kind: 'code' },
    { name: 'Semantic fallback', detail: 'pgvector search, only when the crosswalk finds nothing', kind: 'code' },
    { name: 'Code decision', detail: 'Deterministic scoring selects the billed code', kind: 'decision' },
    { name: 'Audit comparison', detail: 'AI code against the human code, with DRG impact flags', kind: 'code' },
    { name: 'Financials', detail: "The organisation's pricing produces the claim total", kind: 'code' },
    { name: 'Risk and record', detail: 'Risk scored; case, result and audit trail saved', kind: 'code' },
];

export interface Candidate {
    code: string;
    description: string;
    score: number;
}

export interface CaseResult {
    id: string;
    group: string;
    title: string;
    lesson: string;
    footnote?: string;
    noteExcerpt: string[];
    evidence: string;
    code: string;
    description: string;
    score: number;
    resolvedBy: string;
    candidates: Candidate[];
    procedure?: { code: string; description: string; charge: string };
}

export const RESULTS: CaseResult[] = [
    {
        id: 'documented',
        group: 'Same condition, different documentation',
        title: 'Complication documented',
        lesson:
            'The chart records polyneuropathy, confirmed by a nerve conduction study, so the specific combination code earns its specificity.',
        footnote:
            'This note also documents stage 3b chronic kidney disease; this run codes the primary diagnosis.',
        noteExcerpt: [
            'Reduced monofilament sensation bilaterally to the mid-calf. Absent ankle reflexes.',
            'Nerve conduction study: distal symmetric sensorimotor polyneuropathy.',
            'DIAGNOSIS: Type 2 diabetes mellitus with diabetic polyneuropathy.',
        ],
        evidence: 'distal symmetric sensorimotor polyneuropathy … Type 2 diabetes mellitus with diabetic polyneuropathy',
        code: 'E11.42',
        description: 'Type 2 diabetes mellitus with diabetic polyneuropathy',
        score: 0.8625,
        resolvedBy: 'Vector search',
        candidates: [
            { code: 'E11.42', description: 'Type 2 diabetes mellitus with diabetic polyneuropathy', score: 0.8625 },
            { code: 'E10.42', description: 'Type 1 diabetes mellitus with diabetic polyneuropathy', score: 0.8423 },
            { code: 'E13.42', description: 'Other specified diabetes mellitus with diabetic polyneuropathy', score: 0.8343 },
        ],
    },
    {
        id: 'ruled-out',
        group: 'Same condition, different documentation',
        title: 'Complications ruled out',
        lesson:
            'The same disease, but this chart explicitly rules out retinopathy, neuropathy and renal disease. The engine refuses to upcode and returns the uncomplicated code.',
        noteExcerpt: [
            'Feet: intact sensation, normal pulses, no ulcers.',
            'Fundus photography: no evidence of diabetic retinopathy.',
            'DIAGNOSIS: Type 2 diabetes mellitus without complications. No evidence of renal disease. No evidence of neuropathy or retinopathy.',
        ],
        evidence: 'no evidence of diabetic retinopathy … Type 2 diabetes mellitus without complications',
        code: 'E11.9',
        description: 'Type 2 diabetes mellitus without complications',
        score: 0.825,
        resolvedBy: 'SNOMED CT crosswalk',
        candidates: [
            { code: 'E11.9', description: 'Type 2 diabetes mellitus without complications', score: 0.825 },
            { code: 'E11.A', description: 'Type 2 diabetes mellitus without complications in remission', score: 0.5384 },
        ],
    },
    {
        id: 'pdf-with-procedure',
        group: 'From a PDF to a billable claim line',
        title: 'Discharge summary PDF with a procedure',
        lesson:
            'Uploaded as a PDF. The diagnosis resolves through semantic search, and the chest X-ray becomes a priced CPT line. Before specificity had to be earned from the chart, this same note resolved to J84.117, a rare interstitial pneumonia it never mentions.',
        noteExcerpt: [
            'Chest X-Ray: Right lower lobe consolidation consistent with pneumonia.',
            'CBC: WBC 14,200 (elevated) with neutrophilia. CRP 96 mg/L.',
            'DIAGNOSIS: Community-acquired pneumonia, right lower lobe.',
        ],
        evidence: 'Community-acquired pneumonia, right lower lobe',
        code: 'J18.9',
        description: 'Pneumonia, unspecified organism',
        score: 0.6512,
        resolvedBy: 'Vector search',
        candidates: [
            { code: 'J18.9', description: 'Pneumonia, unspecified organism', score: 0.6512 },
            { code: 'J18.8', description: 'Other pneumonia, unspecified organism', score: 0.6493 },
            { code: 'Z87.01', description: 'Personal history of pneumonia (recurrent)', score: 0.5146 },
        ],
        procedure: { code: '71045', description: 'Radiologic examination, chest; single view', charge: '₹27.53' },
    },
];
