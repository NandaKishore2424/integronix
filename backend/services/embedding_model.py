"""
services/embedding_model.py — one shared sentence-embedding model per process.

Two pipeline nodes embed text: cpt_resolve (procedures) and icd_embedding
(diagnoses). Each used to load its own copy of all-MiniLM-L6-v2 — one eagerly
at import, one lazily on first use — so a 1 GB instance held the model twice.
Both now share this loader.

It also fixes a deployment bug. Both nodes loaded the model by hub name. The
Docker image bakes the model into /opt/models and runs with HF_HUB_OFFLINE=1,
and an offline lookup by name does not find a copy saved to a plain directory:
inside the image the load raised OSError, so every pipeline run that needed
vector search would have returned UNKNOWN in production. Resolution now
prefers an explicit path, and CI loads the model inside the built image.
"""
import os
import threading
import time

from config import settings
from logger import get_logger

log = get_logger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
BAKED_MODEL_DIR = f"/opt/models/{MODEL_NAME}"

_model = None
_lock = threading.Lock()
_warm_up_state: dict | None = None


def resolve_model_ref() -> str:
    """
    Where to load the model from: the explicit setting, then the copy baked
    into the Docker image, then the hub name (local development only).
    """
    if settings.embedding_model_path:
        return settings.embedding_model_path
    if os.path.isdir(BAKED_MODEL_DIR):
        return BAKED_MODEL_DIR
    return MODEL_NAME


def _load(ref: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(ref)


def get_embedding_model():
    """Load once, thread-safely. Every later call returns the same instance."""
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                ref = resolve_model_ref()
                started = time.perf_counter()
                _model = _load(ref)
                log.info(
                    "embedding_model_loaded",
                    ref=ref,
                    load_ms=int((time.perf_counter() - started) * 1000),
                )
    return _model


def encode(text: str) -> list[float]:
    """Normalised embedding, as the ICD vector index expects."""
    return get_embedding_model().encode(text, normalize_embeddings=True).tolist()


def run_warm_up() -> dict:
    """
    Load the model and run one encode, recording the outcome.

    A failure is recorded rather than raised: the process still starts, and
    /health reports the instance as not ready — which is how an orchestrator
    tells "still starting" apart from "broken".
    """
    global _warm_up_state
    started = time.perf_counter()
    try:
        encode("warm-up")
        _warm_up_state = {"ok": True, "load_ms": int((time.perf_counter() - started) * 1000)}
    except Exception as exc:
        log.error(
            "embedding_model_warm_up_failed",
            ref=resolve_model_ref(),
            error_type=type(exc).__name__,
            error=str(exc)[:200],
        )
        _warm_up_state = {"ok": False, "error_type": type(exc).__name__}
    return _warm_up_state


def warm_up_status() -> dict | None:
    """None if warm-up never ran in this process, else {"ok": bool, ...}."""
    return _warm_up_state
