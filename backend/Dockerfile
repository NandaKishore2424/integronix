# syntax=docker/dockerfile:1

# ── Stage 1: build ────────────────────────────────────────────────────────────
# Wheels are built here with the toolchain available, then only the installed
# packages are copied forward. The compilers, headers and pip cache never
# reach the shipped image.
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Dependencies are their own layer: application edits do not invalidate it, so
# a code-only change rebuilds in seconds instead of reinstalling torch.
COPY requirements.txt .

# The CPU wheel index matters. The default torch wheel bundles CUDA and is
# ~2.5 GB — on a t3.micro that is the difference between deploying and not.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        -r requirements.txt

# Drop bytecode, bundled test suites and headers from site-packages. They are
# never executed at runtime and account for a few hundred MB across torch,
# scipy and sklearn. Smaller image = faster pulls on every deploy.
RUN find /opt/venv -type d -name "__pycache__" -prune -exec rm -rf {} + \
    && find /opt/venv -type d -name "tests" -prune -exec rm -rf {} + \
    && find /opt/venv -type d -name "test" -prune -exec rm -rf {} + \
    && find /opt/venv -name "*.pyc" -delete \
    && find /opt/venv -name "*.pyi" -delete

# Bake the sentence-transformers model into the image. Downloading it at
# startup would mean every container start depends on HuggingFace being
# reachable, and the first request after a deploy would pay the download.
RUN /opt/venv/bin/python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('all-MiniLM-L6-v2').save('/opt/models/all-MiniLM-L6-v2')"


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# tesseract and poppler are runtime dependencies of the OCR fallback for
# scanned PDFs (pytesseract shells out to tesseract; pdf2image to pdftoppm).
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        poppler-utils \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Run as a non-root user. A container escape should not begin with root.
RUN useradd --create-home --uid 10001 appuser

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=appuser:appuser /opt/models /opt/models

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SENTENCE_TRANSFORMERS_HOME=/opt/models \
    HF_HUB_OFFLINE=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

WORKDIR /app
COPY --chown=appuser:appuser . .

# Never ship local state into the image: .env holds real credentials, and the
# venv is a different platform's build. .dockerignore excludes them; this is
# belt and braces in case it is edited.
RUN rm -rf /app/venv /app/.env /app/.pytest_cache /app/__pycache__

USER appuser
EXPOSE 8000

# Readiness, not liveness: the container is only "healthy" once it can
# actually reach the database and serve traffic.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# One worker on purpose. The rate limiter holds state in-process, and a
# t3.micro has one vCPU — extra workers would multiply memory (each loads the
# embedding model) while making the limiter per-worker rather than global.
# --no-access-log: RequestContextMiddleware already emits one structured JSON
# line per request, with the correlation id and duration. Uvicorn's plaintext
# access log duplicates it in a format nothing can parse.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--no-access-log"]
