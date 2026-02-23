from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import get_db_pool, close_db_pool
from routes import icd, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — try to connect to DB; don't crash if unreachable
    try:
        await get_db_pool()
        print("✅ Database connected")
    except Exception as e:
        print(f"⚠️  Database connection failed at startup: {e}")
        print("   Server is starting without DB — endpoints needing DB will fail gracefully.")
    yield
    # Shutdown
    await close_db_pool()



app = FastAPI(
    title="Integronix API",
    description="Revenue Integrity Engine — Agentic ICD-10 Coding, Audit & Revenue Intelligence",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(icd.router, prefix="/api/v1")
