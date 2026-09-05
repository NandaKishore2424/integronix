from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import close_client, get_client
from logger import get_logger
from middleware import RequestContextMiddleware
from routes import analytics, cases, claims, code, health, icd, parse, payers

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — warm the pooled HTTP client and check connectivity once, so a
    # misconfigured deployment is obvious in the logs at boot rather than on
    # the first user request. A failure here is logged, not raised: the
    # process still starts and /health reports the dependency as down, which
    # is what lets an orchestrator distinguish "starting" from "broken".
    try:
        client = await get_client()
        resp = await client.get("/icd_codes", params={"select": "code", "limit": "1"})
        if resp.status_code == 200:
            log.info("startup_database_connected")
        else:
            log.warning("startup_database_unexpected_status", status=resp.status_code)
    except Exception as e:
        log.error("startup_database_unreachable", error=str(e))

    log.info(
        "startup_complete",
        env=settings.app_env,
        auth_enabled=settings.auth_enabled,
        model=settings.groq_model,
        cors_origins=settings.cors_origins_list,
    )
    yield

    await close_client()
    log.info("shutdown_complete")


app = FastAPI(
    title="Integronix API",
    description="Revenue Integrity Engine — Agentic ICD-10 Coding, Audit & Revenue Intelligence",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────
# Order matters: middleware added last runs first (Starlette wraps outward),
# so the request-context middleware must be added AFTER CORS to sit outside
# it. That way a request rejected by CORS still gets a correlation id and an
# access-log line, and every log line inside the request carries the id.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Lets the browser read the correlation id, so the frontend can show it
    # in an error toast and a user can quote it in a bug report.
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestContextMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(icd.router,       prefix="/api/v1")
app.include_router(parse.router,     prefix="/api/v1")
app.include_router(code.router,      prefix="/api/v1")
app.include_router(cases.router,     prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(claims.router,    prefix="/api/v1")
app.include_router(payers.router,    prefix="/api/v1")
