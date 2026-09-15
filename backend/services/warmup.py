"""
services/warmup.py — pay cold-start costs at boot, not on the first request.

The first pipeline run after a restart took ~55 s, against 7–12 s warm. Very
little of that was the LLM. The cost was importing torch and LangGraph and
compiling the graph, loading the embedding model, and Postgres paging pgvector
indexes back into memory after sitting idle — the first similarity queries
timed out and were retried. Whoever sends the first request, often someone
clicking a link, should not be the one who pays for all of that.

Warm-up runs inside the FastAPI lifespan, before the server accepts traffic.
Every step is best-effort: failures are logged and surfaced through /health,
never raised, so a slow or unreachable dependency cannot stop the process from
starting.
"""
import asyncio
import time

from agents.graph import get_compiled_graph
from database import rpc
from logger import get_logger
from services.embedding_model import encode, run_warm_up

log = get_logger(__name__)

_VECTOR_PRIME_TIMEOUT_S = 30.0
_PRIME_TEXT = "community acquired pneumonia"


async def _prime_vector_indexes() -> bool:
    """One similarity query per vector index, so Postgres loads them now."""
    try:
        vector = await asyncio.to_thread(encode, _PRIME_TEXT)
    except Exception as exc:
        log.warning("warm_up_vector_prime_skipped", error_type=type(exc).__name__)
        return False

    icd_literal = "[" + ",".join(f"{x:.6f}" for x in vector) + "]"
    try:
        await asyncio.wait_for(
            asyncio.gather(
                rpc("match_icd_codes", {
                    "query_embedding": icd_literal,
                    "similarity_threshold": 0.99,
                    "match_count": 1,
                }),
                rpc("match_cpt_codes", {
                    "query_embedding": vector,
                    "match_threshold": 0.99,
                    "match_count": 1,
                }),
            ),
            timeout=_VECTOR_PRIME_TIMEOUT_S,
        )
        return True
    except Exception as exc:
        log.warning("warm_up_vector_prime_failed", error_type=type(exc).__name__)
        return False


async def warm_up_services() -> dict:
    """Load the model, compile the graph, prime the vector indexes."""
    started = time.perf_counter()

    model = await asyncio.to_thread(run_warm_up)

    graph_ok = True
    try:
        await asyncio.to_thread(get_compiled_graph)
    except Exception as exc:
        graph_ok = False
        log.error("warm_up_graph_failed", error_type=type(exc).__name__, error=str(exc)[:200])

    vectors_primed = await _prime_vector_indexes() if model.get("ok") else False

    summary = {
        "model_ok": bool(model.get("ok")),
        "model_ms": model.get("load_ms"),
        "graph_ok": graph_ok,
        "vector_indexes_primed": vectors_primed,
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }
    log.info("warm_up_complete", **summary)
    return summary
