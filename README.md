# Integronix — AI Clinical Coding Engine

> AI-powered ICD-10-CM coding engine with SNOMED mapping, DRG-aware risk scoring, and FHIR R4 output.  
> Stack: **FastAPI · LangGraph · Groq (LLaMA 3.3-70B) · Supabase · pgvector · Next.js 14**

---

## 📋 Prerequisites

Make sure you have these installed before starting:

| Tool | Minimum version |
|---|---|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |
| Git | any |

You will also need accounts / API keys for:
- **Supabase** — free tier is fine → [supabase.com](https://supabase.com)
- **Groq API** — free tier → [console.groq.com](https://console.groq.com)

---

## 🚀 First-time Setup (Clone → Run)

### 1. Clone the repo

```bash
git clone https://github.com/<your-org>/integronix.git
cd integronix
```

---

### 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### 2a. Configure backend environment

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
# Groq
GROQ_API_KEY=your_groq_api_key_here

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key_here
SUPABASE_SERVICE_KEY=your_service_role_key_here

# JWT (can be any long random string for local dev)
JWT_SECRET=your_long_random_secret_here
```

> **Where to find Supabase keys:**  
> Supabase Dashboard → Project → Settings → API → `anon` key and `service_role` key

---

### 3. Database Setup (Supabase)

Run the migration files **in order** in the Supabase SQL Editor:

```
migrations/001_enable_extensions.sql
migrations/002_create_icd_codes.sql
migrations/003_create_snomed_tables.sql
migrations/004_create_clinical_cases.sql
migrations/005_create_coding_results.sql
migrations/006_create_audit_log.sql
migrations/007_create_indexes.sql
migrations/008_seed_data.sql
migrations/009_expanded_seed.sql
migrations/010_vector_search_rpc.sql
```

> **How to run:** Supabase Dashboard → SQL Editor → paste file content → Run

After seeding, generate embeddings for vector search:

```bash
# From backend/ with venv active
python3 scripts/generate_embeddings.py
```

---

### 4. Frontend Setup

```bash
cd ../frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
```

Open `.env.local` and set:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key_here
```

---

## ▶️ Running Locally

Open **two terminal windows**:

**Terminal 1 — Backend**
```bash
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
→ API: [http://localhost:8000](http://localhost:8000)  
→ Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev
```
→ UI: [http://localhost:3001](http://localhost:3001)

---

## 🌿 Git Workflow for Teammates

### Step 1 — Create your own branch

**Never push directly to `main`.** Always work on a feature branch:

```bash
# Make sure you're up to date
git checkout main
git pull origin main

# Create your branch (use your name or feature name)
git checkout -b feature/your-feature-name
# Examples:
# git checkout -b feature/pdf-upload
# git checkout -b fix/risk-score-bug
# git checkout -b nanda/frontend-charts
```

---

### Step 2 — Make changes and check status

```bash
# See what files you've changed
git status

# See the actual changes (optional)
git diff
```

---

### Step 3 — Stage and commit

```bash
# Stage specific files
git add backend/agents/my_file.py
git add frontend/src/components/MyComponent.tsx

# OR stage all changes at once
git add .

# Commit with a clear message
git commit -m "feat: add PDF upload support to Node 1"
git commit -m "fix: correct negation detection for kidney disease"
git commit -m "docs: update API response examples"
```

> **Commit message convention:**
> - `feat:` — new feature
> - `fix:` — bug fix
> - `docs:` — documentation only
> - `refactor:` — code change, no feature/fix
> - `test:` — adding or updating tests

---

### Step 4 — Push your branch

```bash
# First push (sets upstream)
git push -u origin feature/your-feature-name

# Subsequent pushes
git push
```

---

### Step 5 — Keep your branch updated

Before pushing or raising a PR, sync with latest `main`:

```bash
git fetch origin
git rebase origin/main
# OR
git merge origin/main
```

---

### Step 6 — Raise a Pull Request

1. Go to the GitHub repo page
2. Click **"Compare & pull request"** for your branch
3. Write a short description of what you did
4. Request review from a teammate
5. **Do not merge your own PR** — wait for review

---

## 📁 Project Structure

```
integronix/
├── backend/
│   ├── agents/           # LangGraph nodes (8 nodes)
│   │   ├── graph.py      # CodingState + graph wiring
│   │   ├── icd_decision.py
│   │   ├── audit_comparison.py
│   │   ├── risk_scoring.py
│   │   └── ...
│   ├── routes/           # FastAPI routes
│   ├── services/         # Groq extraction service
│   ├── scripts/          # generate_embeddings.py
│   ├── main.py           # App entrypoint
│   ├── database.py       # Supabase REST client
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── app/          # Next.js App Router pages
│   │   ├── components/   # 9 UI components
│   │   ├── lib/          # api.ts (fetch wrapper)
│   │   └── types/        # coding.ts (TypeScript types)
│   └── package.json
│
├── migrations/           # Supabase SQL migrations (001–010)
├── docs/
│   └── PROJECT_DOCUMENTATION.md   # Full technical docs
└── README.md             # ← This file
```

---

## 🧪 Quick Smoke Test

With both servers running:

```bash
curl -X POST http://localhost:8000/api/v1/code/run \
  -H "Content-Type: application/json" \
  -d '{
    "raw_text": "Patient has Type 2 diabetes mellitus with chronic kidney disease stage 3. eGFR is 42 mL/min.",
    "human_icd_code": "E11.9"
  }'
```

**Expected:** `"final_icd_code": "E11.22"`, `"financial_delta": 900`, `"drg_flag": "CC_MISSED"`

---

## 🆘 Common Issues

| Issue | Fix |
|---|---|
| `ModuleNotFoundError` | Did you activate venv? `source venv/bin/activate` |
| `GROQ_API_KEY not set` | Check your `.env` file exists and has the key |
| `connection refused` on port 8000 | Backend isn't running — start it first |
| Frontend shows "Pipeline failed" | Backend must be on port 8000; check the terminal |
| `pgvector` RPC returns 0 results | Run `generate_embeddings.py` after seeding |
| Supabase `401 Unauthorized` | `SUPABASE_KEY` in `.env` is wrong or expired |

---

## 📖 Full Documentation

See [`docs/PROJECT_DOCUMENTATION.md`](docs/PROJECT_DOCUMENTATION.md) for:
- Complete architecture diagram
- All 8 LangGraph nodes explained
- Database schema
- Scoring algorithm details
- All bugs found and fixed
- Stress test results (9/9 passing)
