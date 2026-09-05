# Integronix

[![CI](https://github.com/NandaKishore2424/integronix/actions/workflows/ci.yml/badge.svg)](https://github.com/NandaKishore2424/integronix/actions/workflows/ci.yml)

A clinical coding and revenue-integrity engine. Feed it a discharge summary —
typed or a scanned PDF — and it independently derives the ICD-10 and CPT codes,
compares them against whatever a human coder billed, and quantifies where the
money and the compliance risk are.

**Stack:** FastAPI · LangGraph · Groq · pgvector · Supabase (Postgres + RLS) ·
Next.js 14 · Docker

---

## The problem

Medical coding is the layer between "a doctor wrote something in a chart" and
"the hospital gets paid". Someone has to read prose written for clinicians and
turn it into billing codes.

Get it wrong in one direction and the hospital undercharges — a documented
complication is missed and the reimbursement tier drops. Get it wrong in the
other and you have committed billing fraud under the False Claims Act. Human
coders do this at volume, under time pressure, from notes that were never
written with a coder in mind.

Integronix produces a second, independent opinion: codes, the evidence behind
each one, a confidence score, and a plain diff against the human's answer.

---

## The design decision that matters

**The LLM never picks the billing code.**

It runs in exactly one node, `clinical_extract`, where it turns prose into
structured diagnoses and procedures — each anchored to the sentence it came
from. Every step after that, including the code that determines what gets
billed, is a deterministic scoring function:

```python
score = (confidence  * 0.40      # how well the ontology matched
       + specificity * 0.30      # earned, not free — see below
       + consistency * 0.20      # do the code's words appear in the evidence?
       + combination * 0.10      # ICD-10 prefers combination codes
       + negation)               # penalty when the chart rules it out
```

The reasoning is boring and load-bearing: if a payer disputes a claim, *"the
model was confident"* is not a defensible answer. *"Here is the rule that fired,
and here is the sentence in the chart it fired on"* is.

### Specificity has to be earned

This is the part I would want a reviewer to look at.

When the vector search first came online, the golden pneumonia note resolved to
**J84.117 — "Desquamative interstitial pneumonia"** instead of plain **J18.9**.
Not because the model was confident about a rare interstitial lung disease, but
because `_specificity_score` was `len(code) * 0.15`. A seven-character code
outscored a five-character one for being longer.

That is algorithmic upcoding — the precise failure this system exists to
prevent. The fix implements the actual ICD-10-CM guideline: *code to the highest
level of specificity supported by the documentation*.

```python
def _distinguishing_support(candidate, entities, raw_text) -> float:
    """Fraction of the code's distinguishing clinical terms the chart supports."""
    tokens = [w for w in _description_tokens(candidate["description"])
              if w not in META_WORDS]        # "unspecified", "organism" describe
    if not tokens:                           # the CODE, not the patient
        return 1.0
    hay = raw_text.lower() + " " + evidence_text_of(entities)
    return sum(1 for w in tokens if w in hay) / len(tokens)
```

`specificity = base * (0.35 + 0.65 * support)`. The chart never says
"desquamative" or "interstitial", so J84.117 earns almost none of its length
bonus and J18.9 wins. Feed it a note that *does* document the rare variant and
the specific code wins instead — the rule is **prefer documented**, not
**prefer general**. Both directions are pinned by tests.

### And the negation check

```python
NEGATION_PHRASES = ["no evidence of", "without complications", "ruled out", ...]
```

If a candidate implies a complication ("with diabetic chronic kidney disease")
but the chart says "no evidence of renal disease", it takes a hard penalty.
Without this, a keyword matcher happily bills a complication code off the very
sentence that rules it out.

There is a test note (`samples/03_negation_trap.txt`) built entirely from
negations. It resolves to `E11.9` — *without complications* — as it must.

---

## Pipeline

```
note (text or PDF)
  → doc_processing      pdfplumber, Tesseract OCR fallback for scans
  → clinical_extract    LLM: prose → structured diagnoses + procedures
  → cpt_resolve         procedures → CPT/HCPCS via vector search
  → snomed_resolve      diagnosis → SNOMED concept
  → snomed_icd_map      SNOMED → ICD crosswalk (deterministic)
       ├─ mapping found ─────────────┐
       └─ no mapping → icd_embedding │   (pgvector; runs only when needed)
                                      ▼
                                icd_decision      ← the billing decision
                                      ↓
                                audit_comparison  AI vs. human code
                                      ↓
                                risk_scoring      confidence + $ delta
                                      ↓
                                financial_calc    org pricing → claim total
```

`icd_embedding` loads a transformer and runs a vector query — the most
expensive step in the graph — so the routing after `snomed_icd_map` is a
conditional edge that skips it entirely when the crosswalk already answered.

Every node is wrapped in `@safe_node`, which does two things: records the
failure into state instead of taking the request down, **and short-circuits
every node after it.**

That second half matters more than it sounds. Before it existed, one node
crashing let four more run against half-built state, each failing on `None`,
and the endpoint returned **HTTP 200 with a confident-looking empty result**.
For a billing engine, silently converting a failure into a plausible success is
the worst available outcome. A run that fails now cannot be submitted as a
claim: the API verifies server-side that the session completed and produced a
usable code before it will accept one.

---

## Correctness in the money path

These are the parts I would defend line by line.

**Adjudication is one transaction, not three.** It used to be fetch → check
status in Python → update. Two concurrent approvals both passed the check and
both won. PostgREST cannot hold a transaction across requests, so the invariant
moved into Postgres ([`021_atomic_adjudication.sql`](migrations/schema/021_atomic_adjudication.sql)):
the status check rides inside the `UPDATE`'s `WHERE` clause as an optimistic
lock, and the HIPAA audit row commits in the same transaction or not at all.

```sql
UPDATE public.claims
   SET status = p_new_status, adjudicated_at = now(), ...
 WHERE id = p_claim_id
   AND status = p_expected_status;      -- the lock

IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'status_conflict', ...);
END IF;

INSERT INTO public.claim_audit_logs (...);   -- same transaction
```

The loser of a race gets `409`, not a second payment. Verified by firing two
concurrent approvals at one claim: exactly one `ok`, one `status_conflict`, one
audit row.

**Money is `Decimal`, never `float`.** `0.1 + 0.2 != 0.3` in binary floating
point and the drift accumulates across line items until an EDI 835 fails to
balance. Amounts are quantized to cents with `ROUND_HALF_UP`, built via
`Decimal(str(x))` so a float's binary error is not imported along with it, and
**patient responsibility is the remainder of allowed − paid**, never its own
percentage — so the three amounts reconcile exactly, for every input.

**The audit trail is not best-effort.** A claim with no audit row is not a
representable state: if the audit write fails, the claim is deleted and the
request errors, rather than leaving an untracked claim in a payer queue.

**Tenant isolation is enforced at the application boundary and in the
database.** `Principal.organization_id` is read from the database using the
verified JWT subject — never from the request. A client-supplied `organization_id`
that disagrees is rejected, and `assert_org()` returns *the caller's own* org so
routes use that value and never thread an unchecked one into a query.

---

## Vector search

Two things are embedded: SNOMED concepts and ICD codes, as 384-dimensional
vectors (`all-MiniLM-L6-v2`), queried through pgvector.

The reason it exists is that doctors do not write in ICD terminology. A chart
says "ticker gave out", not "cardiac arrest". Keyword search returns nothing;
cosine similarity finds the right concept anyway. But it is deliberately the
*fallback* — the crosswalk is deterministic and faster when it has an answer.

**Only the 36,401 billable leaf codes are embedded**, not all 98,244. The
decision node discards non-billable candidates anyway, so embedding them would
be paying storage for rows that can never win — and the vectors have to fit
inside a 500 MB free-tier database.

The keyword search underneath has a relevance floor, and it is there for a
specific reason. A pneumonia note was once billed as **S30.810, "Abrasion of
lower back and pelvis"**: the note said "right *lower* lobe", the single token
"lower" substring-matched "lower back", and every index hit scored a flat 0.8
regardless of how little of the query it covered. Matches are now scored by
query coverage against a floor, and returning nothing is an acceptable answer —
the pipeline reports `UNKNOWN`, which it refuses to bill.

---

## Ingestion

Neither ontology is a hardcoded lookup table; both are ETL pipelines against
the real release formats.

**ICD-10-CM** ([`scripts/run_icd_ingestion.py`](backend/scripts/run_icd_ingestion.py))
parses the CDC/NCHS annual release — a fixed-width order file plus XML for
hierarchy and index. The non-obvious decision: billable status is *not* taken
from the source. It is computed as `leaf_codes = all_codes − parent_codes`,
because only leaf codes are billable, which is how payer clearinghouses
actually reject claims. One run loaded 98,186 codes and 46,881 hierarchy nodes,
discarding 6,955 redirect-only entries.

**SNOMED CT** ([`scripts/import_snomed_rf2.py`](backend/scripts/import_snomed_rf2.py))
streams the RF2 release line by line — ~350K concepts, 1.5M relationships —
because loading it into one dataframe simply stalls.

The embedding backfill writes via `COPY` into a temp table plus one join-`UPDATE`
per batch. Per-row updates cost a network round trip each (~4 minutes per 1,000
rows against a hosted database); the same batch now lands in seconds.

---

## Interoperability

- **FHIR R4** — builds a proper HL7 `Claim` resource, choosing the coding-system
  URI (ICD-11 MMS vs. `icd-10-cm`) from the path that actually resolved the
  code, not an org-level default.
- **EDI 837P / 835** — raw ANSI X12 segments written to the `005010X222A1`
  spec, the format US payers legally require. Details that are easy to get
  wrong and matter: money must be `541.00`, never `541`; provider names are
  stripped of anything colliding with the `*` `~` `:` delimiters; and if a DOB
  was not extracted, the segment is **omitted rather than filled with a
  placeholder** — a fabricated DOB is worse than a missing one.

---

## Testing

```bash
cd backend
pytest                 # 210 hermetic tests, no network, ~13s — what CI runs
pytest -m integration  # + live Supabase and Groq
pytest --cov           # with coverage
```

**236 tests in two tiers, and the split is enforced rather than documented.**
`config.Settings` raises on missing credentials, so `conftest.py` substitutes
placeholders before any app module imports; anything needing real I/O is marked
`integration` and skips itself when credentials are absent.

CI therefore runs with **no secrets configured at all** — a green build is
evidence the unit tier is genuinely hermetic. When a "unit" test quietly starts
reaching the network, CI goes red instead of the failure appearing on someone
else's machine.

Because every data access goes through one async layer, a single seam
substitutes the whole database, so route logic — tenant checks, fail-closed
guards, optimistic locks, audit compensation — is tested in milliseconds. Those
tests assert **the shape of the query the route issued**, not just the status
code: an optimistic lock is only a lock if the status predicate is really in
the `WHERE` clause, and a `200` cannot tell you that.

### What mocks cannot check

A fake database enforces no foreign keys and no `CHECK` constraints, so route
logic can be entirely correct and still wrong about the schema. That happened:
claim submission wrote `changed_by_user_id = principal.user_id`, a perfectly
valid UUID — but that column references `auth.users`, while `user_id` is a
`public.users` row id. 209 green tests said nothing; Postgres rejected it on
the first real submission.

[`tests/test_schema_contract.py`](backend/tests/test_schema_contract.py) now
asserts the database facts the code depends on: that FK's target, that every
status string the code writes is permitted by the constraint, that migration
021's functions exist, and that no payer is orphaned. Repointing that FK breaks
a test instead of production.

Coverage is 48% overall and deliberately uneven — highest where a mistake costs
money:

| Module | Coverage |
|---|---|
| `services/fhir_claim_builder.py` | 96% |
| `models.py` | 95% |
| `services/edi_837_builder.py` | 89% |
| `services/payer_policy_gate.py` | 89% |
| `services/edi_835_builder.py` | 86% |

The remainder is offline ETL and pipeline nodes covered by the integration tier.

---

## Operations

**Health checks are split, because the questions differ.** `/health/live`
touches nothing downstream — failure means *restart me*. `/health` checks the
database — failure means *stop routing to me*, and returns **503**, because
load balancers read status codes, not response bodies.

**Every request carries a correlation id**, propagated through a `ContextVar` so
every log line during that request is tagged without any function forwarding it
— a `ContextVar` rather than a global precisely because one event loop serves
many requests concurrently. It is returned as `X-Request-ID` and quoted in
error responses, so "my submission failed" becomes a `grep`.

**The pipeline endpoints are rate limited** with a per-user token bucket. A
fixed window would allow the full quota on either side of a boundary; a bucket
caps the sustained rate while permitting the burst a human clicking a button
produces. Keyed on user rather than IP, since a hospital NAT shares one address.
It is in-process, not Redis — with a single instance that is exact, and the
trigger to move it is recorded in the module rather than left implicit.

---

## Running it

**Prerequisites:** Python 3.12, Node 20 + pnpm, a Supabase project, a Groq API key.

```bash
# Backend
cd backend
python -m venv venv && venv/bin/pip install -r requirements.txt
cp .env.example .env          # fill in Supabase + Groq
venv/bin/uvicorn main:app --reload --port 8000

# Frontend
cd frontend
pnpm install
cp .env.local.example .env.local
pnpm dev
```

Apply `migrations/schema/*.sql` in order, then `migrations/seeds/*.sql`. Run
`scripts/run_icd_ingestion.py` and `scripts/generate_embeddings.py` to populate
the ontologies.

**Containerised:**

```bash
cd backend && docker compose up --build
```

Multi-stage build — dependencies compile in a builder stage and only the
finished virtualenv ships. The CPU torch wheel is selected explicitly (the
default bundles CUDA at ~2.5 GB) and the embedding model is baked in at build
time, so a container start does not depend on HuggingFace being reachable. Runs
as a non-root user; configuration arrives at run time, so one image is promoted
unchanged between environments.

---

## Layout

```
backend/
  agents/      10 LangGraph nodes + graph.py (CodingState, wiring)
  routes/      code, claims, icd, parse, payers, cases, analytics, health
  services/    EDI + FHIR builders, ontology ingestion, payer policy gate
  scripts/     ICD/SNOMED ETL, embedding generation
  tests/       236 tests — 210 hermetic, 26 integration
frontend/      Next.js 14 App Router — hospital and payer portals
migrations/    20 schema migrations + seeds
samples/       synthetic notes for exercising the pipeline
```

32 endpoints. 31 require authentication; `/health` and `/health/live` are public
by design.

---

## Try it

`samples/` holds three synthetic notes:

| Note | Result | Why it is there |
|---|---|---|
| `01_pneumonia_simple` | `J18.9` + CPT 71045 | The happy path, with a billable procedure |
| `02_diabetes_with_complication` | `E11.42` | Specificity the chart **does** document — the specific code correctly wins |
| `03_negation_trap` | `E11.9` | Specificity the chart **rules out** — must refuse to upcode |

Run 2 and 3 back to back. Same disease; the only thing separating the specific
code from the general one is what the documentation supports. One direction is
lost revenue, the other is fraud.

---

Built by Nanda Kishore R, with Subashini S and Nathin R, for the Virtusa Jatayu
Hackathon — and substantially rebuilt since.
