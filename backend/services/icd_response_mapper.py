"""
Normalize ICD-10 and ICD-11 results to a unified response shape.
"""
from __future__ import annotations


def _default_reimbursement(value: float | None) -> float:
    return float(value) if value is not None else 5000.0


def normalize_icd10(results: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for r in results:
        normalized.append(
            {
                "code": r.get("code"),
                "description": r.get("description"),
                "source": "ICD-10",
                "score": float(r.get("score") or 0.0),
                "is_billable": bool(r.get("is_billable")),
                "is_cc": bool(r.get("is_cc", False)),
                "is_mcc": bool(r.get("is_mcc", False)),
                "base_reimbursement": _default_reimbursement(r.get("base_reimbursement")),
            }
        )
    return normalized


def normalize_icd11(results: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for r in results:
        normalized.append(
            {
                "code": r.get("code"),
                "description": r.get("description"),
                "source": "ICD-11",
                "score": float(r.get("score") or 0.0),
                "is_billable": bool(r.get("is_billable")),
                "is_cc": bool(r.get("is_cc", False)),
                "is_mcc": bool(r.get("is_mcc", False)),
                "base_reimbursement": _default_reimbursement(r.get("base_reimbursement")),
            }
        )
    return normalized
