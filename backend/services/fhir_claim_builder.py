"""
FHIR R4 Claim Proposal Builder
Produces a standards-compliant FHIR Claim JSON from Integronix pipeline output.

Design decisions (locked 2026-03-20):
- ICD system: use whatever the hospital chose (ICD-11 or ICD-10). No translation.
- EDI 837: derived later (V1.2) from the payer-verified claim, not from this proposal.
- This is an internal "defense artifact" stored in claim_data.fhir_claim_proposal.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

# ICD coding system URIs (FHIR standard)
_ICD_SYSTEM_MAP = {
    "ICD-11": "http://id.who.int/icd/release/11/mms",
    "ICD-10": "http://hl7.org/fhir/sid/icd-10-cm",
    "ICD-10-CM": "http://hl7.org/fhir/sid/icd-10-cm",
    # Paths that indicate WHO ICD-11 was used
    "who_api_icd11": "http://id.who.int/icd/release/11/mms",
    "who_api_icd10": "http://hl7.org/fhir/sid/icd-10-cm",
    # Local DB paths → ICD-10-CM
    "local_embedding": "http://hl7.org/fhir/sid/icd-10-cm",
    "provider_fallback": "http://hl7.org/fhir/sid/icd-10-cm",
    "provider_augmented": "http://hl7.org/fhir/sid/icd-10-cm",
}

_CPT_SYSTEM = "http://www.ama-assn.org/go/cpt"


def _icd_system_for(icd_version: Optional[str], mapping_path: Optional[str]) -> str:
    """Return the correct FHIR coding system URI based on pipeline output."""
    if mapping_path and mapping_path in _ICD_SYSTEM_MAP:
        return _ICD_SYSTEM_MAP[mapping_path]
    if icd_version and icd_version in _ICD_SYSTEM_MAP:
        return _ICD_SYSTEM_MAP[icd_version]
    return _ICD_SYSTEM_MAP["ICD-10-CM"]


def build_fhir_claim_proposal(
    *,
    claim_id: str,
    session_id: str,
    organization_id: str,
    organization_name: str,
    payer_id: str,
    payer_name: str,
    patient_name: Optional[str],
    patient_dob: Optional[str],
    patient_sex: Optional[str],
    icd_codes: list,
    cpt_codes: list,
    financial_summary: dict,
    icd_version: Optional[str],
    mapping_path: Optional[str],
    total_billed_amount: float,
) -> dict:
    """
    Build a FHIR R4 Claim resource (hospital proposed artifact).

    Parameters
    ----------
    claim_id           : UUID string of the newly created claim row
    session_id         : coding session UUID
    organization_id    : hospital org UUID
    organization_name  : human-readable hospital name
    payer_id           : payer UUID
    payer_name         : human-readable payer name
    patient_name       : extracted patient full name (may be None)
    patient_dob        : extracted DOB in YYYY-MM-DD (may be None)
    patient_sex        : M/F/other (may be None)
    icd_codes          : list of dicts with keys {code, description}
    cpt_codes          : list of dicts (may include keys {cpt_code} or {code}) with description/prices
    financial_summary  : dict from pipeline (line_items, total_billed_amount, etc.)
    icd_version        : "ICD-11" | "ICD-10" (from org_settings)
    mapping_path       : pipeline mapping resolution path
    total_billed_amount: total billed float

    Returns
    -------
    FHIR R4 Claim dict (JSON-serialisable)
    """
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    icd_system = _icd_system_for(icd_version, mapping_path)

    # ── Patient resource (inline contained) ──────────────────────────────────
    patient_resource: dict = {
        "resourceType": "Patient",
        "id": "patient-1",
    }
    if patient_name:
        parts = patient_name.strip().split(" ", 1)
        patient_resource["name"] = [
            {
                "use": "official",
                "text": patient_name,
                "family": parts[-1] if len(parts) > 1 else patient_name,
                "given": [parts[0]] if len(parts) > 1 else [],
            }
        ]
    if patient_dob:
        patient_resource["birthDate"] = patient_dob
    if patient_sex:
        sex_map = {"M": "male", "F": "female", "OTHER": "other", "UNKNOWN": "unknown"}
        patient_resource["gender"] = sex_map.get(patient_sex.upper(), "unknown")

    # ── Diagnosis entries ─────────────────────────────────────────────────────
    diagnosis_entries = []
    for idx, icd in enumerate(icd_codes or []):
        code = icd.get("code") or icd.get("ai_icd_code") or ""
        desc = icd.get("description") or ""
        entry: dict = {
            "sequence": idx + 1,
            "diagnosisCodeableConcept": {
                "coding": [
                    {
                        "system": icd_system,
                        "code": code,
                        "display": desc,
                    }
                ],
                "text": desc,
            },
        }
        if idx == 0:
            entry["type"] = [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/ex-diagnosistype",
                            "code": "principal",
                        }
                    ]
                }
            ]
        diagnosis_entries.append(entry)

    # ── Procedure/item entries ────────────────────────────────────────────────
    line_items = financial_summary.get("line_items") or []
    item_entries = []
    # Be tolerant: pipeline line_items use `code`, while some earlier/other paths may use `cpt_code`.
    cpt_lookup = {}
    for c in (cpt_codes or []):
        key = c.get("cpt_code") or c.get("code") or ""
        if key:
            cpt_lookup[str(key)] = c

    for idx, item in enumerate(line_items):
        cpt_code = item.get("cpt_code") or item.get("code") or ""
        cpt_meta = cpt_lookup.get(str(cpt_code), {})
        base_price = float(
            item.get("gross_charge") or 
            item.get("base_price") or 
            item.get("cms_base_price") or 0.0
        )

        item_entry: dict = {
            "sequence": idx + 1,
            "productOrService": {
                "coding": [
                    {
                        "system": _CPT_SYSTEM,
                        "code": cpt_code,
                        "display": cpt_meta.get("description") or item.get("description") or "",
                    }
                ]
            },
            "unitPrice": {
                "value": round(base_price, 2),
                "currency": "INR",
            },
            "net": {
                "value": round(base_price * float(item.get("quantity") or 1), 2),
                "currency": "INR",
            },
        }
        # Link item to diagnosis
        if diagnosis_entries:
            item_entry["diagnosisSequence"] = [1]
        item_entries.append(item_entry)

    # ── Assemble FHIR Claim ───────────────────────────────────────────────────
    fhir_claim: dict = {
        "resourceType": "Claim",
        "id": claim_id,
        "meta": {
            "profile": ["http://hl7.org/fhir/StructureDefinition/Claim"],
            "lastUpdated": now_iso,
            "tag": [
                {
                    "system": "http://integronix.io/tags",
                    "code": "hospital-proposed",
                    "display": "Hospital Proposed — not yet payer-verified",
                }
            ],
        },
        "text": {
            "status": "generated",
            "div": (
                f"<div xmlns=\"http://www.w3.org/1999/xhtml\">"
                f"Integronix hospital-proposed claim for session {session_id}. "
                f"ICD system: {icd_system}. Not payer-verified."
                f"</div>"
            ),
        },
        "status": "active",
        "type": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/claim-type",
                    "code": "institutional",
                    "display": "Institutional",
                }
            ]
        },
        "use": "claim",
        "patient": {
            "reference": "#patient-1",
            **({"display": patient_name} if patient_name else {})
        },
        "created": now_iso,
        "insurer": {
            "display": payer_name,
            "identifier": {"value": payer_id},
        },
        "provider": {
            "display": organization_name,
            "identifier": {"value": organization_id},
        },
        "priority": {
            "coding": [
                {
                    "code": "normal",
                    "system": "http://terminology.hl7.org/CodeSystem/processpriority",
                }
            ]
        },
        "diagnosis": diagnosis_entries,
        "item": item_entries,
        "total": {
            "value": round(total_billed_amount, 2),
            "currency": "INR",
        },
        # Contained patient resource so the Claim is self-contained
        "contained": [patient_resource],
        # Integronix-specific extensions (non-breaking)
        "extension": [
            {
                "url": "http://integronix.io/fhir/StructureDefinition/session-id",
                "valueString": session_id,
            },
            {
                "url": "http://integronix.io/fhir/StructureDefinition/icd-version",
                "valueString": icd_version or "ICD-10",
            },
            {
                "url": "http://integronix.io/fhir/StructureDefinition/mapping-path",
                "valueString": mapping_path or "unknown",
            },
            {
                "url": "http://integronix.io/fhir/StructureDefinition/proposal-status",
                "valueString": "HOSPITAL_PROPOSED",
            },
        ],
    }

    return fhir_claim
