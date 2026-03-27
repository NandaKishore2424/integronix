from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import get_client, close_client
from routes import icd, health, parse, code, cases, analytics, claims, payers


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — warm up the HTTP client
    try:
        client = await get_client()
        # Quick connectivity test
        resp = await client.get("/icd_codes", params={"select": "code", "limit": "1"})
        if resp.status_code == 200:
            print("✅ Supabase REST API connected")
        else:
            print(f"⚠️  Supabase responded with status {resp.status_code}")
    except Exception as e:
        print(f"⚠️  Supabase connection warning: {e}")
        print("   Server starting without DB verification — check env vars.")
    yield
    # Shutdown
    await close_client()


app = FastAPI(
    title="Integronix API",
    description="Revenue Integrity Engine — Agentic ICD-10 Coding, Audit & Revenue Intelligence",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(icd.router,       prefix="/api/v1")
app.include_router(parse.router,     prefix="/api/v1")
app.include_router(code.router,      prefix="/api/v1")
app.include_router(cases.router,     prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(claims.router,    prefix="/api/v1")
app.include_router(payers.router,    prefix="/api/v1")
