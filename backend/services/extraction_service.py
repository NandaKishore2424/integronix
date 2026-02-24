"""
services/extraction_service.py — Hardened Clinical Entity Extraction via Groq LLM.

Hardening features:
  - Timeout via asyncio.wait_for (configurable via settings)
  - Max 1 retry on timeout or rate limit
  - Token usage logged on every call
  - Latency measured and logged
  - Custom exceptions: ExtractionError, LLMTimeoutError, LLMRateLimitError
  - Model + version tracked in result metadata

Key rule: LLM extracts clinical text ONLY. It NEVER generates ICD codes.
"""
import json
import asyncio
from groq import AsyncGroq, RateLimitError
from config import settings
from models import ExtractionResult
from exceptions import ExtractionError, LLMTimeoutError, LLMRateLimitError
from logger import get_logger, Timer

log = get_logger(__name__)

_groq_client: AsyncGroq | None = None


def _get_groq_client() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=settings.groq_api_key)
    return _groq_client


EXTRACTION_SYSTEM_PROMPT = """You are a clinical medical coding assistant.
Your ONLY job is to extract and structure clinical information from medical text.

STRICT RULES:
- DO NOT generate ICD codes
- DO NOT generate CPT codes
- DO NOT make clinical decisions
- Extract ONLY what is explicitly documented in the text
- If information is not present, use null

Return ONLY valid JSON matching the schema exactly. No explanation, no markdown, just JSON."""

EXTRACTION_USER_PROMPT = """Extract clinical entities from this medical document.

Return this exact JSON structure:
{{
  "diagnoses": [
    {{
      "text": "full clinical description of the diagnosis",
      "severity": "mild | moderate | severe | acute | chronic | null",
      "laterality": "left | right | bilateral | null",
      "snomed_candidate": {{
        "code": "SNOMED concept ID if known, or null",
        "description": "best clinical term for this diagnosis"
      }},
      "comorbidities": ["list of comorbid conditions mentioned alongside this diagnosis"],
      "evidence_text": "exact quote from the document supporting this diagnosis"
    }}
  ],
  "observations": [
    {{
      "loinc_description": "lab test name (eGFR, creatinine, HbA1c, etc.)",
      "value": "numeric or text value",
      "unit": "unit string or null"
    }}
  ]
}}

MEDICAL DOCUMENT:
{raw_text}"""


async def _call_groq(raw_text: str) -> dict:
    """
    Single Groq API call, wrapped with asyncio timeout.
    Returns parsed JSON dict.
    """
    client = _get_groq_client()
    truncated = raw_text[:8000] if len(raw_text) > 8000 else raw_text

    with Timer() as timer:
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=settings.groq_model,
                    messages=[
                        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user",   "content": EXTRACTION_USER_PROMPT.format(raw_text=truncated)},
                    ],
                    temperature=0.0,
                    max_tokens=settings.groq_max_tokens,
                    response_format={"type": "json_object"},
                ),
                timeout=settings.groq_timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise LLMTimeoutError(
                f"Groq call timed out after {settings.groq_timeout_seconds}s",
                model=settings.groq_model,
            )
        except RateLimitError as e:
            raise LLMRateLimitError(f"Groq rate limit: {e}", model=settings.groq_model)

    # Log token usage and latency
    usage = response.usage
    log.info(
        "groq_call_success",
        model=settings.groq_model,
        model_version=settings.groq_model_version,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        total_tokens=usage.total_tokens if usage else 0,
        latency_ms=timer.elapsed_ms,
    )

    raw_json = response.choices[0].message.content
    try:
        return json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise ExtractionError(f"LLM returned invalid JSON: {e}", raw_response=raw_json[:200])


async def extract_clinical_entities(
    raw_text: str,
    session_id: str = "",
) -> tuple[ExtractionResult, dict]:
    """
    Extract structured clinical entities from raw text using Groq LLM.
    Returns (ExtractionResult, extraction_metadata).
    Retries once on timeout or rate limit.
    Raises ExtractionError if all attempts fail.
    """
    last_error: Exception | None = None

    for attempt in range(settings.groq_max_retries + 1):
        try:
            if attempt > 0:
                log.warning(
                    "groq_retry",
                    attempt=attempt,
                    session_id=session_id,
                    reason=str(last_error),
                )

            parsed = await _call_groq(raw_text)
            result = ExtractionResult(**parsed)

            metadata = {
                "model": settings.groq_model,
                "llm_version": settings.groq_model_version,
                "icd_version": settings.icd_version,
                "snomed_version": settings.snomed_version,
                "attempt": attempt + 1,
            }
            return result, metadata

        except (LLMTimeoutError, LLMRateLimitError) as e:
            last_error = e
            continue  # retry

        except ExtractionError:
            raise  # don't retry bad JSON

        except Exception as e:
            raise ExtractionError(f"Unexpected LLM error: {e}", session_id=session_id)

    raise ExtractionError(
        f"All {settings.groq_max_retries + 1} attempts failed: {last_error}",
        session_id=session_id,
    )
