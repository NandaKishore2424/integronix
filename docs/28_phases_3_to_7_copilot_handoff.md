# Integronix — Remaining Work Handoff (Phases 3–7)

> Use this with **VSCode Copilot** — recommended model: **GPT-4o** (most accurate for multi-file backend + DevOps tasks)

---

## Completed So Far

- ✅ Phase 1 — WHO ICD API integrated (`services/who_icd_service.py`, rewired Nodes 3/4/5)
- ✅ Phase 2 — `org_settings` table live in Supabase (migration 019 ran, seeded with ICD-11)

---

## Phase 3 — Auto-Cache WHO API Results into `icd_codes` table

**Goal:** When WHO API returns a code not in our DB, auto-insert it. DB becomes a warm cache over time.

### What to do

**File:** `backend/database.py` — add this function:

```python
async def upsert_icd_code_from_who(code: str, title: str, version: str) -> None:
    """Cache a WHO API result into icd_codes. Skips if code already exists."""
    # Use supabase upsert with on_conflict="code"
    # Fields: code, description, icd_version, is_billable=True, source="who_icd_api"
    # is_cc=False, is_mcc=False, base_reimbursement=5000.0 (default until manually set)
```

**File:** `backend/services/who_icd_service.py` — after successful search in `_search_icd11_mms()`, add:

```python
import asyncio
# After results list is built, fire-and-forget cache upsert:
for r in results:
    asyncio.create_task(
        upsert_icd_code_from_who(r["code"], r["description"], version)
    )
```

### How to verify

1. Start backend: `uvicorn main:app --reload --port 8000`
2. Submit a case in the frontend Analyze page
3. Go to Supabase → Table Editor → `icd_codes`
4. New rows should appear with `source = 'who_icd_api'`

---

## Phase 3 — Dashboard Development

**Goal:** Implement the missing dashboard page with KPIs and charts.

### What was created

**File:** `frontend/src/app/dashboard/page.tsx`

- Created a new dashboard page.
- Integrated reusable components (`AuditCard`, `CandidateChart`).
- Fetches analytics data using `getAnalyticsOverview` and `getTopCodes`.
- Displays KPIs, trends, and top ICD codes.

### How to verify

1. Start the frontend: `npm run dev`.
2. Navigate to `/dashboard`.
3. Verify:
   - KPI cards display financial delta and discrepancies.
   - Top ICD codes chart is populated.
   - No errors are shown.

---

## Phase 4 — Dockerise Backend

**Goal:** Package the backend into a Docker image for GCP deployment.

### What to create

**File:** `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y tesseract-ocr libgl1-mesa-glx && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
COPY . .
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**File:** `backend/.dockerignore`

```
venv/
__pycache__/
*.pyc
.env
*.egg-info
```

### How to verify

```bash
cd backend
docker build -t integronix-backend .
docker run -p 8080:8080 --env-file .env integronix-backend
# Then open: http://localhost:8080/health  → should return {"status": "ok"}
# Also test: http://localhost:8080/docs    → Swagger UI should load
```

---

## Phase 5 — GCP Cloud Run Deployment

**Goal:** Deploy backend to Google Cloud Run (free tier, Mumbai region).  
**Cost:** ₹0 — fits within free tier (2M req/month).

### Prerequisites

- Install [gcloud CLI](https://cloud.google.com/sdk/docs/install)
- Docker installed and running

### Step-by-step commands

```bash
# 1. Login and create project
gcloud auth login
gcloud projects create integronix-prod --name="Integronix"
gcloud config set project integronix-prod

# 2. Enable APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

# 3. Create Docker registry
gcloud artifacts repositories create integronix --repository-format=docker --location=asia-south1

# 4. Build and push (from backend/ folder)
gcloud builds submit --tag asia-south1-docker.pkg.dev/integronix-prod/integronix/backend:latest .

# 5. Deploy
gcloud run deploy integronix-backend \
  --image asia-south1-docker.pkg.dev/integronix-prod/integronix/backend:latest \
  --platform managed --region asia-south1 \
  --allow-unauthenticated --memory 1Gi --cpu 1 \
  --min-instances 0 --max-instances 3 --timeout 60 \
  --set-env-vars SUPABASE_URL=https://dagtaimloudlbbpxijha.supabase.co,\
SUPABASE_SERVICE_KEY=<paste_key>,\
GROQ_API_KEY=<paste_key>,\
WHO_ICD_CLIENT_ID=13b8eb6e-6fd9-450e-abd5-0b1f8f1ba3c1_709fbfa4-c611-4556-8110-f425129c1384,\
WHO_ICD_CLIENT_SECRET=bq0pcADWt7NmFUMJJ2InXIzjT5zdyGXnX1y4sy4PUyo=,\
APP_ENV=production
```

### How to verify

```bash
# GCP gives you a URL after deploy. Test it:
curl https://<your-cloud-run-url>/health
# Expected: {"status": "ok", "environment": "production"}
```

---

## Phase 6 — Vercel Frontend Deployment

**Goal:** Deploy Next.js frontend to Vercel (free, zero-config, global CDN).

### Step-by-step

```bash
cd frontend
npm install -g vercel
vercel --prod
# Follow prompts — link to your GitHub repo
```

### Environment variables to set in Vercel Dashboard

Go to: **Vercel → Project → Settings → Environment Variables**

| Key                             | Value                                         |
| ------------------------------- | --------------------------------------------- |
| `NEXT_PUBLIC_API_URL`           | `https://<your-cloud-run-url>`                |
| `NEXT_PUBLIC_SUPABASE_URL`      | `https://dagtaimloudlbbpxijha.supabase.co`    |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | _(from Supabase → Settings → API → anon key)_ |
| `NEXT_PUBLIC_DEMO_EMAIL`        | `demo@integronix.ai`                          |
| `NEXT_PUBLIC_DEMO_PASSWORD`     | _(your demo password)_                        |

### Update CORS — `backend/main.py`

Find the `allow_origins` list and add your Vercel URL:

```python
allow_origins=[
    "http://localhost:3000",
    "https://integronix.vercel.app",      # add this
    "https://<exact-project>.vercel.app", # add this too
]
```

Then redeploy backend: repeat the `gcloud run deploy` command from Phase 5.

### How to verify

- Open Vercel URL → landing page loads
- Login works
- No CORS errors in browser console (F12 → Network tab)

---

## Phase 7 — End-to-End Hosted Test

Run through this checklist on the live hosted app:

| Test                                   | Expected Result                                     |
| -------------------------------------- | --------------------------------------------------- |
| Login as `demo@integronix.ai`          | Dashboard loads                                     |
| Analyze → paste clinical text → Submit | Result shows ICD-11 code (e.g. `5A11`, not `E11.x`) |
| Check `mapping_path` in result         | Should say `who_api_icd11`                          |
| Upload a PDF                           | Result loads within ~5 seconds                      |
| Case History page                      | Shows submitted cases                               |
| Analytics page                         | Charts load with data                               |
| Check Supabase `icd_codes` table       | New rows with `source = 'who_icd_api'`              |

---

## Model Recommendation for Copilot

| Task                              | Recommended Model               | Why                                       |
| --------------------------------- | ------------------------------- | ----------------------------------------- |
| **Phase 3** (Python backend code) | **GPT-4o**                      | Best at multi-file Python, async patterns |
| **Phase 4** (Dockerfile)          | **GPT-4o** or Claude 3.5 Sonnet | Simple but precision matters              |
| **Phase 5** (GCP CLI + Cloud Run) | **GPT-4o**                      | Knows gcloud CLI syntax accurately        |
| **Phase 6** (Vercel + Next.js)    | **GPT-4o**                      | Native Next.js knowledge                  |
| **Phase 7** (Debugging)           | **Claude 3.5 Sonnet**           | Better at reading error traces            |

> **General rule:** Use **GPT-4o** for writing new code. Use **Claude 3.5 Sonnet** if you get stuck on a bug.  
> In Copilot Chat: type `/` to switch models. Select `GPT-4o` from the model picker.

---

## Key Files Reference

| File                                              | Purpose                                |
| ------------------------------------------------- | -------------------------------------- |
| `backend/services/who_icd_service.py`             | WHO ICD API client                     |
| `backend/agents/snomed_resolver.py`               | Node 3 — calls WHO API                 |
| `backend/config.py`                               | All settings including WHO credentials |
| `backend/.env`                                    | Actual credential values               |
| `docs/26_who_icd_integration_and_hosting_plan.md` | Full plan with progress tracker        |
| `docs/27_who_icd_api_integration_reference.md`    | WHO API technical reference            |
| `migrations/019_org_settings.sql`                 | ✅ Already run in Supabase             |
