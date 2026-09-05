# Integronix

[![CI](https://github.com/NandaKishore2424/integronix/actions/workflows/ci.yml/badge.svg)](https://github.com/NandaKishore2424/integronix/actions/workflows/ci.yml)

AI-powered clinical coding and revenue-integrity engine for hospitals. Feed it a clinical note (typed or a scanned PDF) and it independently figures out the ICD-10/11 and CPT codes, then compares its answer against whatever a human coder billed and tells you exactly where the money and the risk are.

Stack: **FastAPI · LangGraph · Groq (gpt-oss-120b) · WHO ICD-API · SNOMED CT · pgvector · Supabase (Postgres + RLS) · Next.js 14**

Built by Team AgentsCrew (Nanda Kishore R, Subashini S, Nathin R) for the Virtusa Jatayu Hackathon.

## The problem

Medical coding is the layer between "doctor wrote something in a chart" and "hospital gets paid." Get it wrong in one direction and the hospital undercharges — miss a documented complication and the reimbursement tier is lower than it should be. Get it wrong the other way and you've committed billing fraud under the False Claims Act. Human coders do this at volume, under time pressure, from notes that are rarely written with a coder in mind.

Integronix runs the same note through an AI pipeline and produces a second, independent opinion — codes, evidence, confidence, and a plain-English diff against the human's code: did the AI find a complication that got missed, or is the human's code more specific than the chart actually supports.

## How the pipeline works

This is the part I'd actually want a reviewer to look at. It's a 10-step LangGraph pipeline, and the interesting design decision is *where* the LLM is allowed to touch the outcome and where it explicitly isn't.

```
note (text or PDF)
  → doc_processing        PyMuPDF, falls back to Tesseract OCR for scanned charts
  → clinical_extract      Groq/Llama-3.3-70B pulls structured diagnoses + procedures,
                           each one anchored to the exact sentence it came from
  → cpt_resolve           procedures → CPT codes
  → snomed_resolve        diagnosis text → SNOMED CT concept, via vector search
  → snomed_icd_map        SNOMED → ICD crosswalk (deterministic lookup table)
       ├─ mapping found ───────────────┐
       └─ no mapping → icd_embedding   │   (pgvector fallback, skipped otherwise)
                                        ▼
                                  icd_decision   ← the actual billing decision, see below
                                        ↓
                                  audit_comparison   AI code vs. human code
                                        ↓
                                  risk_scoring       confidence + $ delta → LOW/MED/HIGH
                                        ↓
                                  financial_calc     org pricing multiplier → claim total
```

`CodingState` is a single TypedDict that gets passed node to node and accumulates fields as it goes — think of it as the chart itself moving down an assembly line. Every node is wrapped in a `@safe_node` decorator so one node blowing up writes an error into the state instead of taking the whole request down.

The routing after `snomed_icd_map` is a conditional edge, not a straight line: if the crosswalk already found a code, the pipeline skips `icd_embedding` entirely and goes straight to the decision node. `icd_embedding` runs a `SentenceTransformer` model and a pgvector query — it's the most expensive step in the graph, so it only runs when it's actually needed. That's a genuinely useful latency win, not just a nice diagram.

## Where the LLM stops and math takes over

This is the decision I'm most confident about: **the LLM never picks the billing code.** It's only used in one node — `clinical_extract` — to turn messy prose into structured diagnoses. Everything after that, including the final code that determines what gets billed, comes from a plain scoring function in `icd_decision.py`:

```python
def _final_score(candidate: dict, entities: dict, raw_text: str = "") -> float:
    confidence   = float(candidate.get("confidence", 0.85))
    specificity  = _specificity_score(candidate, entities)
    consistency  = _clinical_consistency_score(candidate, entities)
    combination  = _combination_code_priority(candidate)
    negation     = _negation_penalty(candidate, entities, raw_text)

    score = (
        confidence  * 0.40 +
        specificity * 0.30 +
        consistency * 0.20 +
        combination * 0.10 +
        negation
    )
    return round(max(0.0, min(score, 1.0)), 4)
```

The reasoning is boring but important: if a payer disputes a claim, "the model felt confident" isn't a defensible answer — you need to be able to point at the exact rule that produced the code. So confidence from the ontology match matters, but so does code specificity (a 7-character code capturing "with diabetic nephropathy" outranks the bare 3-character category), and so does whether the words in the code's description actually show up in the evidence text the LLM extracted.

The part I actually like is the negation check:

```python
def _negation_penalty(candidate, entities, raw_text=""):
    description = candidate.get("description", "").lower()
    is_complication_code = _kw_match(description, [
        r"\bwith\b", "complicated by", "chronic kidney", "neuropathy", "failure", "retinopathy"
    ])
    if not is_complication_code:
        return 0.0
    combined_text = (entity_text + " " + raw_text.lower()).strip()
    for phrase in NEGATION_PHRASES:   # "no evidence of", "without complications", ...
        if phrase in combined_text:
            return -0.4
    return 0.0
```

If a candidate code implies a complication ("with diabetic chronic kidney disease") but the chart itself says "no evidence of renal disease," that candidate takes a hard penalty. Without this, an LLM-driven pipeline will happily upcode based on a keyword match and call it a day — which is exactly the kind of mistake that gets flagged in a compliance audit. It's a small function, but it's the difference between "AI demo" and something you could actually defend to a hospital's compliance officer.

## Vectorization — why, and where it earns its keep

Two things get embedded: SNOMED concepts and ICD codes, both as 384-dim vectors via `sentence-transformers` (`all-MiniLM-L6-v2`), stored and queried through `pgvector`/Supabase RPCs.

The reason vector search exists at all is that doctors don't write in ICD terminology. A chart says "ticker gave out," not "cardiac arrest." Keyword or `ilike` search returns nothing for that. Cosine similarity over sentence embeddings finds the right concept anyway, because the two phrases land near each other in embedding space even with zero shared words. That's genuinely doing work here, not just there for the sake of using a vector DB — but it's also the *fallback*, not the primary path, precisely because it's probabilistic and the crosswalk table is deterministic and faster when it's available.

## The ingestion pipelines

Neither the ICD nor the SNOMED data is a hardcoded lookup table — both are ETL pipelines against the real, messy government/standards-body release formats.

**ICD-10-CM** (`scripts/run_icd_ingestion.py`) parses the CDC/NCHS annual release: a fixed-width `.txt` order file for codes, and two XML files for the hierarchy and the alphabetical index. The one non-obvious decision here: billable status is *not* taken from the source file — it's computed after the fact by loading the full parent/child hierarchy and taking `leaf_codes = all_codes − parent_codes`. Only leaf codes are billable, which matches how real payer clearinghouses actually reject claims. One production run of this loaded 98,186 codes, 46,881 hierarchy nodes, and 70,385 search-index terms, filtering out 6,955 redirect-only/invalid entries along the way.

**SNOMED CT** (`scripts/import_snomed_rf2.py`) does the same thing against the SNOMED CT International RF2 release — around 350,000 active concepts and 1.5M relationships, streamed line-by-line from the raw TSVs (loading that into a single dataframe just stalls), bulk-inserted in batches, then embedded. Generating 350K embeddings on a CPU takes most of a day; batching it onto a GPU brings that down to roughly half an hour.

## Interoperability and security

- **FHIR R4** — `services/fhir_claim_builder.py` builds a proper HL7 `Claim` resource, and picks the right coding-system URI (WHO ICD-11 MMS vs. `icd-10-cm`) based on which resolution path actually produced the code, not just an org-level default.
- **EDI 837P / 835** — `services/edi_837_builder.py` writes raw ANSI X12 segments (`ISA*...~`, `CLM*...~`, etc.) by hand to the `005010X222A1` spec, which is the format US payers legally require. Details that matter here and are easy to get wrong: money has to be formatted as exactly `541.00`, never `541`; hospital names get stripped of anything that could collide with the `*`/`~`/`:` delimiters; and if a patient's DOB wasn't extracted from the chart, the segment is just omitted rather than filled with a placeholder — a fabricated DOB is worse than a missing one from a compliance standpoint.
- **Row-Level Security** — every table with PHI has a policy like `organization_id = current_user_org_id()`, where that function reads `organization_id` out of the verified JWT claims and runs `SECURITY DEFINER` so it can't be sidestepped. This means tenant isolation is enforced by Postgres itself — even a bug in the FastAPI layer can't leak Hospital A's data to Hospital B, because the database won't return the rows in the first place.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), React, TypeScript, Tailwind, Recharts |
| API | FastAPI, async Python 3.11+ |
| Orchestration | LangGraph |
| LLM | Groq — `openai/gpt-oss-120b`, used for extraction only |
| Ontologies | WHO ICD-API v2, SNOMED CT (RF2), CDC/NCHS ICD-10-CM |
| Vector search | pgvector + sentence-transformers (`all-MiniLM-L6-v2`) |
| Database | Supabase / Postgres 16, Auth, RLS |
| Document parsing | pdfplumber + pytesseract OCR fallback |
| Claims formats | HL7 FHIR R4, ANSI X12 EDI 837/835 |

## Project layout

```
backend/
  agents/       the 10 LangGraph nodes + graph.py (CodingState + wiring)
  routes/       code, claims, icd, parse, payers, cases, analytics
  services/     EDI builders, FHIR builder, ICD/SNOMED ingestion, payer policy gate
  scripts/      run_icd_ingestion.py, import_snomed_rf2.py, embedding generators
  tests/        195 tests — 182 unit (hermetic, CI-gated) + 13 integration

frontend/
  src/app/          Next.js pages
  src/components/   AuditCard, RiskMeter, DrgBadge, FhirPanel, MultiCodeList, ...
  src/lib/, src/types/

migrations/
  schema/  tables + RLS policies
  seeds/   demo data
```

27 REST endpoints across `code` (run the pipeline), `claims` (submit/adjudicate/appeal/export EDI), `icd`, `parse`, `payers`, `cases`, and `analytics`.

## Running it locally

**Backend**
```bash
cd backend
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, DATABASE_URL, GROQ_API_KEY
```

**Database** — run everything in `migrations/schema/` in order via the Supabase SQL editor, then:
```bash
python3 scripts/generate_embeddings.py
```

**Frontend**
```bash
cd frontend
pnpm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL, NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_DEMO_EMAIL, NEXT_PUBLIC_DEMO_PASSWORD
```

**Run both**
```bash
# backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload   # docs at /docs

# frontend
pnpm dev   # localhost:3000
```

**Smoke test**
```bash
curl -X POST http://localhost:8000/api/v1/code/run \
  -H "Content-Type: application/json" \
  -d '{
    "raw_text": "Patient has Type 2 diabetes mellitus with chronic kidney disease stage 3. eGFR is 42 mL/min.",
    "human_icd_code": "E11.9"
  }'
```
Expect `final_icd_code: "E11.22"` with `drg_flag: "CC_MISSED"` — the pipeline caught a complication the human code (`E11.9`, unspecified) didn't capture.

## Tests

```bash
cd backend
pytest                    # 182 unit tests, no network, ~3s — what CI runs
pytest -m integration     # + live Supabase and Groq (needs real credentials)
pytest --cov              # with a coverage report
```

The suite is split into two tiers, and the split is enforced rather than
documented: `config.Settings` raises on missing credentials, so `conftest.py`
substitutes placeholders before any app module is imported. Anything that
genuinely needs the network is marked `integration` and **skips itself** when
real credentials are absent.

That means CI runs with **no secrets configured at all** — a green build is
evidence the unit suite is actually hermetic. When a test quietly starts
reaching out to Supabase, CI goes red instead of the failure showing up on
someone else's machine. (That has already happened once: a helper doing
`from database import select_one` held its own binding and slipped past the
fixture — green locally, red in CI, which is exactly the point.)

Because every data access goes through one async layer (`database.py`), one
seam substitutes the whole database. Route logic — tenant checks, fail-closed
guards, optimistic-lock filters, compensation on audit failure — is tested in
milliseconds against a fake, and the tests assert the *shape of the query* the
route issued, since an optimistic lock is only a lock if the status predicate
is really in the `WHERE` clause.

Coverage is deliberately uneven. It is highest where a mistake costs money:

| Module | Coverage | Why it matters |
|---|---|---|
| `services/fhir_claim_builder.py` | 96% | claim artifact |
| `models.py` | 95% | request bounds on money fields |
| `services/edi_837_builder.py` | 89% | the file payers legally require |
| `services/payer_policy_gate.py` | 89% | decides auto-approval of payment |
| `services/edi_835_builder.py` | 86% | remittance advice |

Most of the remainder is offline ETL (`icd_parsers`, `icd_loader_service`)
and pipeline nodes exercised by the integration tier.

## Running it in a container

```bash
cd backend
docker compose up --build          # reads backend/.env, serves on :8000
```

The image is multi-stage: dependencies compile in a builder stage and only the
finished virtualenv is copied into the runtime image, so no compiler ships to
production. Two details that matter more than they look:

- **The CPU torch wheel is selected explicitly.** The default `torch` wheel
  bundles CUDA and is ~2.5 GB on its own — on a `t3.micro` that is the
  difference between deploying and not.
- **The embedding model is baked into the image at build time.** Otherwise
  every container start depends on HuggingFace being reachable, and the first
  request after a deploy pays the download.

It runs as a non-root user, and configuration arrives at *run* time via
environment variables rather than being built in, so one image is promoted
unchanged from local to production. CI builds the image on every push and
smoke-tests it — that it starts, binds, answers `/health/live`, correctly
reports 503 readiness with no database, and still returns 401 on protected
routes.

## Operability

**Health checks are split, because the two questions have different answers.**

| Probe | Question | On failure |
|---|---|---|
| `/health/live` | Is the process alive? Touches nothing downstream. | restart me |
| `/health` | Can this instance serve? Checks the database. | stop routing to me |

Conflating them turns a brief database blip into a restart loop. The readiness
probe previously returned **200 unconditionally**, putting `"database":
"error"` in the body — load balancers read the status code, so a fully broken
instance stayed in rotation. It now returns 503.

**Every request carries a correlation id.** Middleware stamps each request
with an id, propagates it through a `ContextVar` so every log line emitted
while serving that request is tagged automatically, and returns it as
`X-Request-ID`. Error responses quote it, so "my submission failed" becomes
`grep <id>` and the whole path through the system falls out. An inbound id is
honoured (so a trace spans the proxy) but only after validation — it reaches
the logs, and an unvalidated value is a log-injection vector.

**The pipeline endpoints are rate limited** with a per-user token bucket.
A fixed window would let a caller fire the full quota either side of a window
boundary; a bucket refills continuously, capping the sustained rate while
still allowing the short burst a human clicking a button actually produces.
It is in-process, not Redis — with one instance that is exact, and a network
dependency would buy nothing. The trigger to move it is a second instance,
and that reasoning is recorded in `rate_limit.py` rather than left implicit.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | venv isn't active |
| `GROQ_API_KEY not set` | `.env` missing or incomplete |
| pgvector RPC returns nothing | run `generate_embeddings.py` after seeding |
| Supabase `401` | `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_KEY` wrong or expired |

## More docs

`docs/` has the deeper writeups — the full decision algorithm, database schema, SNOMED/WHO integration notes, ingestion runbooks. It is kept **local-only** (gitignored), so it is not present in a fresh clone.

## Contributing

Branch off `main`, conventional commit prefixes (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`), PRs reviewed before merge.
