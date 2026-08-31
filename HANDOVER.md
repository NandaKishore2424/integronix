# Integronix — Session Handover

**Date:** 2026-08-29
**Branch:** `main` (local `1f913b6`, identical to `origin/main` — nothing pushed)
**State:** all work is **uncommitted in the working tree**. Nothing has been committed or pushed.

---

> ### ⚠️ Correction added 2026-08-31 — verified against the live system
>
> The claim below that the 8 test failures "should pass once `GROQ_MODEL` is set to an
> available model" is **wrong**. Verified by running it: setting
> `GROQ_MODEL=openai/gpt-oss-120b` takes the suite from **8 failures to 5**, not to 0.
>
> With a working model the pipeline completes with **no `error_at`** — and still returns
> `final_icd_code: "UNKNOWN"`, `confidence: 0.0`, `icd_codes: []`. All three routes to an
> ICD code are dead for a second, independent reason: **missing data**.
>
> | Route | State |
> |---|---|
> | WHO ICD API (primary) | No credentials — `WHO_ICD_CLIENT_ID`/`_SECRET` absent from `.env` |
> | `snomed_icd_map` crosswalk | **5 rows** |
> | pgvector fallback | **0 of 98,244** `icd_codes` rows have an `embedding` (column is NULL throughout; same for all 379,283 `snomed_concepts`) |
>
> Bulk ingestion loaded fine; the **embedding-generation step never ran**. Until it does,
> the vector search this README headlines is a no-op. Fixing the model is necessary but
> not sufficient.
>
> Also verified: migration `020_jwt_org_claim.sql` has **not** been applied — all three
> `auth.users` still have `app_metadata.organization_id = None`.

## 🚨 Read this first — the pipeline is currently dead

`GROQ_MODEL` defaults to `llama-3.3-70b-versatile` in [`backend/config.py`](backend/config.py).
**That model returns 404 from Groq for this account.** Verified directly:

```
Error code: 404 - The model `llama-3.3-70b-versatile` does not exist or you do not have access to it.
```

Listing the account's available models returns **14, none of them Llama**:

```
openai/gpt-oss-120b
openai/gpt-oss-20b
qwen/qwen3.6-27b
qwen/qwen3.8-27b
```

Nothing was changed about this — picking the model for a medical-coding system is a
decision with real quality consequences and it is yours to make. Fix is one line
in `.env`:

```bash
GROQ_MODEL=openai/gpt-oss-120b
```

**Every one of the 8 remaining test failures is downstream of this.** The extraction
node gets a 404, returns nothing, and four subsequent nodes crash on `None`.

---

## Test status

```
33 passed, 8 failed
```

Run with:

```bash
cd backend && venv/bin/python -m pytest tests/ -q
```

The 8 failures are all `TestCodeRunEndpoint::test_golden_*` — they need a working
LLM. They should pass once `GROQ_MODEL` is set to an available model. **Re-run them
before assuming anything else is broken.**

Note: these are integration tests. They hit the live Supabase and the live Groq API.
There is still no test that can run in CI without credentials.

---

## What was done, in order

### 1. Repo sync (no changes)
`origin/main` and local `main` are both at `1f913b6`. Verified live with `git ls-remote`,
not just the cached ref. There was nothing to pull.

### 2. Environment repair

- `tesseract-ocr` 5.3.4 installed (by you).
- The `pip` half of your `&&` chain never ran — `pdf2image`, `pytest`, `pytest-asyncio`
  were still missing. Installed them. **OCR is now live end-to-end**
  (`pdf2image` → `pytesseract` → tesseract 5.3.4). `torch` untouched at `2.13.0+cpu`.
- This let the test suite run for the first time.

### 3. Cleanups

| Area | Change |
|---|---|
| `backend/.env.example` | Rewritten — was missing every key `config.py` requires; a fresh `cp .env.example .env` crashed on startup. Verified it now boots. |
| `backend/requirements.txt` | Added `groq`, `pdf2image`, `pytest`, `pytest-asyncio`, `PyJWT`, `cryptography`. Removed unused `asyncpg`, `langchain`, `pgvector`. |
| Dead files | Deleted `backend/code.py` (1-line orphan shadowing the stdlib `code` module), empty `.cursor/`, `page.module.css`, `next.svg`, `vercel.svg`, `components.json` (shadcn config with no shadcn installed), stock `frontend/README.md`. |
| Lockfiles | Kept `pnpm-lock.yaml`, deleted `package-lock.json`. `node_modules/next` is a symlink into `.pnpm/` — pnpm built the tree. Pinned `"packageManager": "pnpm@10.17.1"`. |
| Env examples | Kept `frontend/.env.local.example`, deleted the stale `frontend/.env.example`. |
| Seeds | `003_e2e_demo_seed.sql` → `004_e2e_demo_seed.sql` (was a duplicate `003`). `git mv`, history preserved. |
| `README.md` | Removed phantom `JWT_SECRET`, fixed both `cp` lines, `npm`→`pnpm`, port 3001→3000, `SUPABASE_KEY`→`SUPABASE_ANON_KEY`, marked `docs/` as local-only. |

### 4. Security work (the bulk of the session)

See **Findings** below for why. What changed:

**New: [`backend/auth.py`](backend/auth.py)**
- `Principal` — a verified caller: `auth_id`, `organization_id`, `role`, `org_type`, `token`.
  The org comes **from the database, never from the request**.
- `verify_token()` — local HS256 verification when `SUPABASE_JWT_SECRET` is set;
  otherwise falls back to the Supabase Auth API (`/auth/v1/user`), which is
  authoritative and algorithm-agnostic. Both paths cached 60s.
- `get_principal` — the FastAPI dependency.
- `require_roles(...)`, `require_payer_org()` — role/org-type gates.
- `Principal.assert_org(org_id)` — the tenant check. Returns the caller's own org, so
  routes use the return value and never thread the client-supplied one onward.
- Fails closed: unreachable auth service → 503, not a pass.

**Modified: [`backend/database.py`](backend/database.py)**
- `_headers(user_token=None)` — service role, or the caller's token.
- `select_as_service()` — **explicitly** RLS-bypassing. Named so every bypass is greppable.
- `select_for(principal, ...)` — tenant-scoped, forwards the JWT when enabled.
- `request_headers(principal)` — header builder for forwarded requests.

**Modified: [`backend/config.py`](backend/config.py)** — new settings:
`supabase_jwt_secret`, `auth_enabled` (default `true`), `dev_org_id`,
`db_forward_user_jwt` (default `false` — see the migration warning below).

**New: [`migrations/schema/020_jwt_org_claim.sql`](migrations/schema/020_jwt_org_claim.sql)** — **not yet run.**
- Backfills `auth.users.raw_app_meta_data.organization_id` and adds a trigger to keep it synced.
- Hardens `current_user_org_id()` to read the claim from either location.
- Adds `UNIQUE INDEX uq_claims_session_id` — closes the double-billing race.

**Routes** — all 8 routers wired. Verified programmatically:

```
PROTECTED : 26
PUBLIC    :  1   → GET /health   (correct)
```

**Frontend: [`frontend/src/lib/api.ts`](frontend/src/lib/api.ts)**
- Added `apiFetch()` which injects `Authorization: Bearer <supabase access token>`
  and redirects to `/auth/login` on 401.
- All 19 backend call sites now route through it. No other file calls the backend.

### 5. Bugs found and fixed along the way

- **`/api/v1/icd/search` was unreachable.** `@router.get("/{code}")` was declared first,
  so FastAPI matched `search` as an ICD code and 404'd. Reordered; `{code}` is now last
  with a comment explaining why.
- **Missing claims returned 500, not 404.** PostgREST `.single()` *raises* PGRST116 on zero
  rows, so every `if not res.data: raise 404` guard was unreachable and the bare
  `except` turned it into a 500. Replaced all 10 `.single()` → `.maybe_single()`.
- **`financial_calculator.py` cross-tenant pricing.** When `org_id` was absent it read
  `org_settings LIMIT 1` — *another tenant's* multiplier — and billed with it. Now falls
  back to `DEFAULT_MULTIPLIER` and logs a warning.
- **Unbounded money fields.** `payer_responsibility_pct` had no bounds (passing `5.0` paid
  5× the allowed amount with negative patient responsibility). Now `Field(ge=0.0, le=1.0)`.
  `total_billed_amount` now `Field(ge=0, le=100_000_000)`. `action` now `Literal["APPROVE","DENY"]`.
- **Error leakage.** `/code/run` returned `f"Pipeline failed: {str(e)}"` to the client.
  Now returns a correlation id; detail goes to the log.
- **Tests.** Fixed stale `/code/run` → `/api/v1/code/run` paths (including f-string ones),
  the `/health` `"ok"` vs `"running"` assertion, and added auth fixtures to `conftest.py`
  (`client`, `payer_client`, `anon_client`, `hospital_principal`, `payer_principal`).

---

## ⚠️ Before you deploy or demo — required steps

### A. Set a working model
```bash
GROQ_MODEL=openai/gpt-oss-120b   # in backend/.env
```

### B. Add the JWT secret (optional but recommended)
```bash
SUPABASE_JWT_SECRET=<Supabase → Settings → API → JWT Secret>
```
Without it auth still works, but every request costs a round-trip to the Supabase Auth API.

### C. `TEST_ORG_ID` for the integration tests
Tenant scoping is now enforced on every query, so the tests need an org that actually has
seeded rows or they will see nothing:
```bash
export TEST_ORG_ID=<org uuid from seeds/002_demo_tenant_and_users.sql>
```

### D. Do NOT enable `DB_FORWARD_USER_JWT` yet
Order matters and getting it wrong locks everyone out of their own data:

1. Run `migrations/schema/020_jwt_org_claim.sql`.
2. **Every user must sign in again.** JWT claims are baked in at issue time; existing
   sessions carry a claim-less token for up to an hour.
3. *Then* set `DB_FORWARD_USER_JWT=true`.

Flipping it before step 2 finishes makes `current_user_org_id()` return NULL, and every
org-isolation policy denies. Application-layer tenant checks work regardless and are
already on — the flag is defence in depth, not the primary control.

---

## Findings — what prompted the security work

### Fixed this session

1. **No backend authentication at all.** All 27 endpoints were public. `get_supabase()` in
   `claims.py` accepted an `Authorization` header, never read it, and was never even wired
   via `Depends()` — security theatre that read as solved.
2. **Tenant isolation bypassed.** 9 RLS policies were correctly written, then bypassed
   everywhere by the service-role key. The only separation between hospitals was the
   `org_id` the caller put in the URL.
3. **`app_metadata.organization_id` is never populated** — so `current_user_org_id()` has
   always returned NULL and **those RLS policies have never actually enforced anything.**
   They were dormant, not protecting. This is what migration 020 fixes.
4. **Cases and Analytics never filtered by org at all** — six endpoints returned every
   tenant's coded cases, revenue and risk scores by default. No crafted request needed;
   that was the normal behaviour of those pages.

### Still open — not addressed, deliberately

**These were reported and not implemented. They are the recommended next work.**

1. **🔴 A failed pipeline run returns HTTP 200 and can be billed.**
   [`node_runner.py`](backend/agents/node_runner.py) catches every exception, sets
   `error_at`, and lets the graph continue. **Nothing downstream checks `error_at`.**
   This reproduced live this session: the Groq 404 caused `snomed_resolve`, `icd_decision`,
   `risk_scoring` and `financial_calc` to all crash — and the endpoint still returned 200
   with a confident-looking empty result.
   The frontend shows a passive "Review required at:" banner but nothing blocks submission.
   **Fix:** short-circuit the graph on `error_at`, and refuse claim submission for any
   session carrying it.
   This is the same shape as the OCR fallback silently returning `""` — the system
   systematically converts failures into plausible-looking successes, which for a billing
   engine is the worst available failure mode.

2. **🟠 No transactions, no idempotency.** `adjudicate` does fetch → check status → update
   with no optimistic lock (TOCTOU; two concurrent APPROVEs both win). Add
   `.eq("status", expected)` to the update and check the affected-row count.

3. **🟠 The HIPAA audit trail is best-effort.** [`claims.py`](backend/routes/claims.py)
   wraps the audit insert in try/except and only logs failure — *after* the claim is
   already marked PAID. `adjudicated_at` is never set at all.

4. **🟠 Money is floats throughout.** Should be `Decimal`. EDI 837/835 amounts must
   reconcile exactly; accumulated drift will eventually produce an unbalanced claim.

5. **🟠 Blocking I/O in async nodes.** `financial_calculator.py` and all 11 `claims.py`
   sites create a *synchronous* supabase client inside `async def` and call `.execute()` —
   this blocks the event loop, and creates a fresh client per request. Meanwhile
   `database.py` has a proper pooled async singleton that the money code doesn't use.
   Two competing data layers; the good one is unused where it matters most.

6. **🟠 PDF DoS.** [`code.py`](backend/routes/code.py) reads the whole upload into memory
   *then* checks the 20 MB limit.

7. **🟠 No rate limiting.** `/code/run` triggers an LLM call. Now authenticated, so no
   longer anonymous spend — but still unmetered per user.

8. **🟡 Prompt injection undefended.** Clinical notes go straight into the LLM user message.
   A crafted note could steer toward a higher-reimbursing code. `temperature=0` and JSON
   mode reduce drift but not instruction-following.

9. **🟡 `coding_mode` logic looks inverted** in `payer_policy_gate.py` — both `aggressive`
   *and* `conservative` tighten thresholds; only `balanced` is neutral, so a conservative
   hospital is penalised relative to a balanced one. Probably not intended.

10. **🟡 Smaller items:** `datetime.utcnow()` deprecated on 3.12; DOB sanity check only
    compares `.year`; `graph.py` swallows the langgraph `ImportError` into a confusing
    `NoneType is not callable`; no log redaction layer (currently careful — logs
    `text_length` not `raw_text` — but `error=str(e)` could pull PHI in); CORS origins
    hardcoded to localhost in `main.py`.

### Worth preserving — this is good code

- **`services/payer_policy_gate.py`** is the strongest module in the repo. Deterministic,
  fails closed, `auto_approve_enabled` defaults false, severity-tagged reasons. Don't
  refactor it casually.
- **LLM integration is disciplined** — temperature 0, forced JSON mode, truncation, retry
  on timeout/ratelimit, explicit `JSONDecodeError` handling.
- The graph is compiled once and cached. Structured logging with per-node timers.
- The RLS policies themselves are correct — they just needed to be *used*.

---

## Verification performed

| Check | Result |
|---|---|
| Backend imports | ✅ 27 endpoints |
| Auth coverage (dependency-tree walk) | ✅ 26 protected, only `/health` public |
| Anonymous requests to 10 endpoints | ✅ all 401 |
| Forged bearer token | ✅ 401 (via the Auth API fallback, against live Supabase) |
| Cross-tenant reads (org A → org B) | ✅ 403 on all 4 paths, denials logged |
| Payer-only endpoints called by hospital user | ✅ 403 |
| `auth.py` primitives (13 assertions) | ✅ all pass |
| Frontend `tsc --noEmit` | ✅ 0 errors |
| Frontend `pnpm build` | ✅ all 18 routes |
| Test suite | ⚠️ 33 passed, 8 failed — **all 8 blocked on the dead Groq model** |

---

## Changed files

**New (untracked):** `backend/auth.py`, `migrations/schema/020_jwt_org_claim.sql`,
`.mcp.json`, this file.

**Modified:** `README.md`, `backend/.env.example`, `backend/config.py`,
`backend/database.py`, `backend/requirements.txt`,
`backend/agents/financial_calculator.py`, `backend/routes/{analytics,cases,claims,code,icd,parse,payers}.py`,
`backend/tests/{conftest,test_e2e_pipeline}.py`, `frontend/src/lib/api.ts`,
`frontend/package.json`, `frontend/README.md`

**Deleted:** `backend/code.py`, `frontend/.env.example`, `frontend/components.json`,
`frontend/package-lock.json`, `frontend/public/{next,vercel}.svg`,
`frontend/src/app/page.module.css`

**Renamed:** `migrations/seeds/003_e2e_demo_seed.sql` → `004_e2e_demo_seed.sql`

Nothing committed. `git diff HEAD` shows everything.

---

## Other notes

- **Supabase MCP is configured but unauthenticated.** `.mcp.json` and
  `.claude/settings.local.json` are set up, project ref `dagtaimloudlbbpxijha` matches
  both `.env` files. Authorize with `claude mcp` in an interactive terminal.
- `.mcp.json` is untracked (you said to leave it). It holds no secrets — only a project
  ref — so it is safe to commit if you want teammates to get the MCP config.
- `frontend/.env.local` is still missing `NEXT_PUBLIC_DEMO_EMAIL` / `NEXT_PUBLIC_DEMO_PASSWORD`.
  The Demo Access button on the login page will submit `undefined` until you add them.
