# 26 — WHO ICD API Integration, Production Data Layer & GCP Hosting Plan

> **Type:** Living Progress Document — update checkboxes as each step completes  
> **Created:** 2026-03-12 | **Last Updated:** 2026-03-12  
> **Owner:** Engineering Team  
> **Goal:** Make Integronix production-ready: WHO ICD API (ICD-11 primary, ICD-10 on request), real data layer, GCP Cloud Run deployment

---

## Progress Tracker

| Phase | Description | Status |
|---|---|---|
| **Phase 1** | WHO ICD API Integration | ✅ **Complete** |
| **Phase 2** | `org_settings` — Per-hospital ICD version config | 🔲 Run migration |
| **Phase 3** | Production data layer (auto-caching from WHO API) | 🔲 Not started |
| **Phase 4** | Dockerise backend | 🔲 Not started |
| **Phase 5** | GCP Cloud Run deployment | 🔲 Not started |
| **Phase 6** | Vercel frontend deployment | 🔲 Not started |
| **Phase 7** | End-to-end hosted test | 🔲 Not started |

---

## ✅ PHASE 1 — WHO ICD API Integration (COMPLETE)

**Verified:** 2026-03-12 — Live WHO ICD API returning real ICD-11 codes  
**Detailed reference:** See [`docs/27_who_icd_api_integration_reference.md`](./27_who_icd_api_integration_reference.md)

### What Was Built

| File | Change |
|---|---|
| `backend/.env` | Added `WHO_ICD_CLIENT_ID`, `WHO_ICD_CLIENT_SECRET`, token endpoint, base URL |
| `backend/config.py` | Added WHO ICD settings block — credentials, release IDs, default version |
| `backend/services/who_icd_service.py` | **NEW** — OAuth2 token cache, MMS search, Foundation search, autocode, normaliser |
| `backend/agents/snomed_resolver.py` | **REWRITTEN** — WHO API as primary path, SNOMED DB as fallback |
| `backend/agents/snomed_icd_mapper.py` | Added early-exit: skips when WHO API already populated candidates |
| `backend/routes/code.py` | Added `icd_version` to initial state for both `/run` and `/run-pdf` |
| `migrations/019_org_settings.sql` | **NEW** — org_settings table with RLS (run in Supabase) |

### Key Fix: Release ID Format
WHO ICD API uses `YYYY-MM` release format. `"2026"` was invalid → `"2026-01"` works.

### Verified Output
```
TEST 1: ICD-11 MMS search — diabetes + CKD      → SUCCESS: 3 results
TEST 2: ICD-11 — acute heart failure              → SUCCESS: 3 results
TEST 3: ICD-11 — essential hypertension           → SUCCESS: 3 results
```

---

## 🔲 PHASE 2 — `org_settings` Per-Hospital ICD Version Config

**Estimated time:** 5 minutes  
**Purpose:** Each hospital can use ICD-11 (default, Ayushman Bharat) or ICD-10 (private legacy)

### Step 2.1 — Run migration in Supabase SQL Editor

**File:** `migrations/019_org_settings.sql`

```
1. Open Supabase dashboard
2. SQL Editor → New Query
3. Copy-paste contents of migrations/019_org_settings.sql
4. Click Run
5. Verify with: SELECT o.name, s.icd_version FROM org_settings s JOIN organizations o ON o.id = s.organization_id;
```

### Step 2.2 — Read org_settings in pipeline (Future Enhancement)

Currently `icd_version` defaults to `"ICD-11"` from config.  
To make it truly per-org, `routes/code.py` should fetch `org_settings` from Supabase for the requesting user's org:

```python
# In run_full_pipeline(), after resolving session_id:
org_row = await select_one("org_settings", "icd_version,coding_mode,claim_scheme",
                            {"organization_id": f"eq.{user_org_id}"})
icd_version = org_row["icd_version"] if org_row else settings.who_icd_default_version
```

- [ ] Run `019_org_settings.sql` in Supabase
- [ ] (Optional) Wire org lookup into code route for true per-org switching

---

## 🔲 PHASE 3 — Production Data Layer (Auto-Cache from WHO API)

**Estimated time:** 1 hour  
**Purpose:** `icd_codes` table becomes a results cache, not a source of truth. Auto-populates from real hospital usage.

### Design
```
WHO API returns code "5A11" (not in our DB)
    → upsert into icd_codes (code, description, icd_version, source="who_icd_api")
    → next query for same code hits local DB instead of WHO API
    → DRG/revenue fields still manually curated (payer-specific, not in WHO API)
```

### Step 3.1 — Add upsert helper to `database.py`
```python
async def upsert_icd_code_from_who(code: str, title: str, version: str):
    """Cache WHO API result. Skips if code already exists."""
    await upsert("icd_codes", {
        "code":         code,
        "description":  title,
        "icd_version":  version,
        "is_billable":  True,
        "source":       "who_icd_api",
    }, on_conflict="code")
```

### Step 3.2 — Call upsert after each successful WHO search
```python
# In who_icd_service.py, after successful search:
for r in results:
    asyncio.create_task(upsert_icd_code_from_who(r["code"], r["description"], version))
```

- [ ] Add `upsert_icd_code_from_who` to `database.py`
- [ ] Wire upsert call in `who_icd_service.py` (background task, non-blocking)
- [ ] Verify codes appear in `icd_codes` table after first pipeline run

---

## 🔲 PHASE 4 — Dockerise Backend

**Estimated time:** 30 minutes  
**File to create:** `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System deps: Tesseract OCR for scanned PDFs
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download sentence-transformers model at build time (saves cold-start time)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**File to create:** `backend/.dockerignore`
```
venv/
__pycache__/
*.pyc
.env
*.egg-info
.pytest_cache/
```

### Test locally before pushing to GCP
```bash
cd backend
docker build -t integronix-backend .
docker run -p 8080:8080 --env-file .env integronix-backend
# Test: curl http://localhost:8080/health
```

- [ ] Create `backend/Dockerfile`
- [ ] Create `backend/.dockerignore`
- [ ] Local Docker build passes
- [ ] Local Docker test: `/health` returns 200

---

## 🔲 PHASE 5 — GCP Cloud Run Deployment

**Estimated time:** 1–2 hours  
**Cost:** ₹0 — fits entirely within GCP free tier

### GCP Free Tier (what we use)
| Service | Free Tier | Our Usage |
|---|---|---|
| Cloud Run | 2M requests/month, 360k GB-sec compute | Backend container |
| Artifact Registry | 0.5GB | Docker images |
| Cloud Build | 120 min/day | Build pipeline |

### Step 5.1 — One-time GCP project setup
```bash
# Install gcloud CLI: https://cloud.google.com/sdk/docs/install

gcloud auth login
gcloud projects create integronix-prod --name="Integronix"
gcloud config set project integronix-prod

gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable artifactregistry.googleapis.com

# Create Docker repo
gcloud artifacts repositories create integronix \
  --repository-format=docker \
  --location=asia-south1 \
  --description="Integronix backend images"
```

### Step 5.2 — Build and push Docker image
```bash
# From backend/ directory (with venv NOT active)
gcloud builds submit \
  --tag asia-south1-docker.pkg.dev/integronix-prod/integronix/backend:latest \
  .
```

### Step 5.3 — Deploy to Cloud Run (Mumbai region)
```bash
gcloud run deploy integronix-backend \
  --image asia-south1-docker.pkg.dev/integronix-prod/integronix/backend:latest \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --timeout 60 \
  --set-env-vars \
    SUPABASE_URL=https://dagtaimloudlbbpxijha.supabase.co,\
    SUPABASE_SERVICE_KEY=<your_service_key>,\
    GROQ_API_KEY=<your_groq_key>,\
    WHO_ICD_CLIENT_ID=<your_who_client_id>,\
    WHO_ICD_CLIENT_SECRET=<your_who_client_secret>,\
    APP_ENV=production
```

> **Region:** `asia-south1` = Mumbai — lowest latency for Indian users.  
> **min-instances: 0** = scales to zero when idle (free). **max-instances: 3** = handles demo load.

### Step 5.4 — Note Cloud Run URL
After deployment, GCP gives a URL like:  
`https://integronix-backend-xxxxxxxxxx-el.a.run.app`

Save this — needed for frontend env vars.

- [ ] Create GCP project `integronix-prod`
- [ ] Enable Cloud Run, Cloud Build, Artifact Registry APIs
- [ ] Build Docker image via Cloud Build
- [ ] Deploy to Cloud Run (`asia-south1`)
- [ ] Test: `curl https://<cloud-run-url>/health` returns `{"status": "ok"}`

---

## 🔲 PHASE 6 — Vercel Frontend Deployment

**Estimated time:** 30 minutes  
**Why Vercel:** Built for Next.js — zero config, free tier, global CDN, auto-SSL.

### Step 6.1 — Deploy
```bash
cd frontend
npx vercel --prod
# Follow prompts: link to GitHub repo if asked
# Vercel auto-deploys on every push to main branch
```

### Step 6.2 — Environment variables in Vercel dashboard

Go to: Vercel Dashboard → Your Project → Settings → Environment Variables

```
NEXT_PUBLIC_API_URL          = https://integronix-backend-xxxxxx-el.a.run.app
NEXT_PUBLIC_SUPABASE_URL     = https://dagtaimloudlbbpxijha.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY = <anon_key_from_supabase_settings>
NEXT_PUBLIC_DEMO_EMAIL       = demo@integronix.ai
NEXT_PUBLIC_DEMO_PASSWORD    = <demo_password>
```

### Step 6.3 — Update CORS in backend `main.py`
```python
allow_origins=[
    "http://localhost:3000",
    "https://integronix.vercel.app",       # your Vercel URL
    "https://<your-project>.vercel.app",   # exact URL from Vercel
]
```

Then redeploy backend:
```bash
gcloud builds submit --tag ... && gcloud run deploy ...
```

- [ ] Deploy frontend via Vercel CLI
- [ ] Set all env vars in Vercel dashboard
- [ ] Update CORS in `main.py` with Vercel URL
- [ ] Redeploy backend with new CORS setting

---

## 🔲 PHASE 7 — End-to-End Hosted Test

**Checklist:**
- [ ] Open Vercel URL → landing page loads without errors
- [ ] Login as `demo@integronix.ai`
- [ ] Navigate to Analyze → paste diabetes + CKD text → submit
- [ ] Confirm result shows ICD-11 code (alphanumeric like `5A11`, not E11.x)
- [ ] `mapping_path` in response should say `who_api_icd11` (not `direct` or `embedding`)
- [ ] Test PDF upload end-to-end
- [ ] Check Case History page shows the test case
- [ ] Check Analytics page loads
- [ ] Run migration `018_cases_history_columns.sql` in Supabase if not done
- [ ] Run migration `019_org_settings.sql` in Supabase if not done

---

## Architecture — After Phase 1 (Current State)

```
Clinical Text / PDF
        │
        ▼
[Node 1] Document Processor (text passthrough or PDF/OCR)
        │
        ▼
[Node 2] Groq LLaMA 3.3-70B — diagnosis text extraction
        │
        ▼
[Node 3] WHO ICD API ← NEW (replaces 17-concept SNOMED lookup)
    → MMS search: /icd/release/11/2026-01/mms/search
    → Returns: ICD-11 codes [{code: "5A11", score: 0.94}, ...]
    → Fallback: Foundation search → SNOMED DB (if WHO API down)
        │
[Node 4] SKIPPED (when WHO API returned results)
        │
[Node 5] SKIPPED (when WHO API returned results)
        │
        ▼
[Node 6] ICD Decision Engine — picks winner, multi-code list
        │
        ▼
[Node 7] Audit Comparison (vs human code if provided)
        │
        ▼
[Node 8] Risk Scoring + FHIR R4 + DB write
        │
        ▼
Frontend: Results Panel, Case History, Analytics
```

---

*Update status column in Progress Tracker as each phase completes.*
