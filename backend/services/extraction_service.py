"""
extraction_service.py — Clinical entity extraction using Groq LLM.

Key rule: LLM is used ONLY for parsing/NLP. It NEVER generates ICD codes.
Output is validated against Pydantic models before use.
"""
import json
import os
from groq import AsyncGroq
from models import ExtractionResult

_groq_client: AsyncGroq | None = None


def _get_groq_client() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
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
        "code": "SNOMED concept ID if you know it, or null",
        "description": "best clinical term for this diagnosis"
      }},
      "comorbidities": ["list of comorbid conditions mentioned alongside this diagnosis"],
      "evidence_text": "exact quote from the document that supports this diagnosis"
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


async def extract_clinical_entities(raw_text: str) -> ExtractionResult:
    """
    Call Groq LLM to extract structured clinical entities from raw text.
    Validates and returns a Pydantic ExtractionResult.
    Raises ValueError if LLM output cannot be parsed or validated.
    """
    client = _get_groq_client()

    # Truncate to avoid token limits (~3000 words max)
    truncated_text = raw_text[:8000] if len(raw_text) > 8000 else raw_text

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": EXTRACTION_USER_PROMPT.format(raw_text=truncated_text),
            },
        ],
        temperature=0.0,       # deterministic output
        max_tokens=2048,
        response_format={"type": "json_object"},
    )

    raw_json = response.choices[0].message.content

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw: {raw_json[:300]}")

    try:
        result = ExtractionResult(**parsed)
    except Exception as e:
        raise ValueError(f"LLM output failed Pydantic validation: {e}")

    return result
