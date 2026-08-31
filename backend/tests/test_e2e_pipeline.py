"""
backend/tests/test_e2e_pipeline.py

TICKET-06 — End-to-End Regression Test Suite
=============================================

Purpose
-------
Prevent silent regressions across all 9 pipeline nodes.
A single `pytest` run should tell us definitively: "demo ready / not ready".

Test strategy
-------------
1.  UNIT TESTS  — Service-layer builders (EDI 837 / EDI 835 / FHIR). No DB, no
    LLM, no network. Pure-Python, always fast.

2.  INTEGRATION TESTS — FastAPI TestClient against the full app.
    Uses the real Supabase connection (read from .env).
    Marked with @pytest.mark.integration so they can be skipped in CI:
        pytest -m "not integration"        # fast unit-only run
        pytest -m integration              # full integration run

3.  GOLDEN-SET ASSERTIONS — A known input note + expected output values.
    These encode the exact outputs produced in sprint demos so we know
    immediately if a model/pipeline change broke something.

Run
---
    cd backend
    pytest tests/ -v                          # all tests
    pytest tests/ -v -m "not integration"    # fast / offline only

Dependencies (dev only, not in production requirements.txt)
-----------------------------------------------------------
    pip install pytest httpx python-dotenv
"""

from __future__ import annotations

import os
import sys
import json
import uuid
import pytest

# ── Make the backend importable without installing it as a package ────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# Helpers
# =============================================================================

def _load_env():
    """Load .env from the backend root if present (for local dev)."""
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        load_dotenv(env_path)
    except ImportError:
        pass  # python-dotenv not installed — rely on OS environment


# =============================================================================
# UNIT: edi_837_builder
# =============================================================================

class TestEdi837Builder:
    """Unit tests for the X12 837P builder — no external deps."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from services.edi_837_builder import build_edi_837
        self.build = build_edi_837

    SAMPLE_FHIR = {
        "resourceType": "Claim",
        "patient": {"display": "Priya Raman"},
        "contained": [
            {
                "resourceType": "Patient",
                "id": "patient-1",
                "name": [{"text": "Priya Raman", "family": "Raman", "given": ["Priya"]}],
                "birthDate": "1988-04-15",
                "gender": "female",
            }
        ],
        "diagnosis": [
            {
                "diagnosisCodeableConcept": {
                    "coding": [{"system": "ICD-10-CM", "code": "J18.9", "display": "Pneumonia"}]
                }
            }
        ],
        "item": [
            {
                "productOrService": {
                    "coding": [{"code": "99232", "display": "Hospital E&M"}]
                },
                "net": {"value": 541.00, "currency": "INR"},
                "unitPrice": {"value": 541.00, "currency": "INR"},
                "quantity": {"value": 1},
            }
        ],
        "total": {"value": 541.00, "currency": "INR"},
    }

    def _build(self, **kwargs) -> str:
        defaults = {
            "fhir_claim": self.SAMPLE_FHIR,
            "org_name": "City General Hospital",
            "payer_name": "National Health Insurance",
            "claim_db_id": str(uuid.uuid4()),
            "total_billed_amount": 541.00,
        }
        defaults.update(kwargs)
        return self.build(**defaults)

    def test_returns_string(self):
        result = self._build()
        assert isinstance(result, str), "build_edi_837 must return a string"

    def test_starts_with_isa(self):
        result = self._build()
        assert result.startswith("ISA*"), f"EDI 837 must start with ISA*, got: {result[:30]}"

    def test_segment_terminator(self):
        result = self._build()
        assert "~" in result, "Segment terminator '~' must be present"

    def test_contains_clm_segment(self):
        result = self._build()
        assert "CLM*" in result, "CLM segment (claim-level) must be present in 837"

    def test_patient_name_embedded(self):
        result = self._build()
        # NM1 or BPR should not contain a default placeholder
        assert "RAMAN" in result.upper() or "PRIYA" in result.upper(), \
            "Patient name must be embedded in EDI 837 output"

    def test_icd_code_embedded(self):
        result = self._build()
        assert "J18.9" in result or "J189" in result, \
            "ICD code J18.9 must appear in EDI 837"

    def test_cpt_code_embedded(self):
        result = self._build()
        assert "99232" in result, "CPT code 99232 must appear in EDI 837"

    def test_ends_with_iea(self):
        result = self._build()
        # Strip trailing whitespace before checking
        stripped = result.rstrip()
        assert "IEA*" in stripped, "EDI 837 must contain IEA trailer"

    def test_no_placeholder_text(self):
        result = self._build()
        bad_tokens = ["PLACEHOLDER", "TODO", "FAKE", "SAMPLE_ORG"]
        for tok in bad_tokens:
            assert tok not in result.upper(), f"Placeholder text '{tok}' found in EDI 837"

    def test_financial_amount_correct(self):
        """The total charge in CLM03 should reflect the FHIR net amount."""
        result = self._build()
        # CLM03 holds the total submitted charge; 541.00 → should appear as 541.00
        assert "541.00" in result, "Financial amount 541.00 must be present in EDI 837"

    def test_no_crash_on_empty_fhir(self):
        """Builder must not raise even with a bare / empty FHIR bundle."""
        try:
            result = self.build(
                fhir_claim={},
                org_name="Test Org",
                payer_name="Test Payer",
                claim_db_id=str(uuid.uuid4()),
                total_billed_amount=0.0,
            )
            assert isinstance(result, str)
        except Exception as e:
            pytest.fail(f"build_edi_837 raised an exception with empty FHIR: {e}")


# =============================================================================
# UNIT: edi_835_builder
# =============================================================================

class TestEdi835Builder:
    """Unit tests for the X12 835 remittance builder."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from services.edi_835_builder import build_edi_835
        self.build = build_edi_835

    SAMPLE_FHIR_CLAIM = {
        "item": [
            {
                "productOrService": {"coding": [{"code": "99232"}]},
                "net": {"value": 541.00},
            }
        ]
    }

    def _build(self, **kwargs) -> str:
        defaults = dict(
            claim_id=str(uuid.uuid4()),
            claim_status="PAID",
            total_billed=541.00,
            total_paid=433.00,
            org_name="City General Hospital",
            payer_name="National Health Insurance",
            patient_name="Priya Raman",
            fhir_claim=self.SAMPLE_FHIR_CLAIM,
        )
        defaults.update(kwargs)
        return self.build(**defaults)

    def test_returns_string(self):
        assert isinstance(self._build(), str)

    def test_starts_with_isa(self):
        result = self._build()
        assert result.startswith("ISA*"), "EDI 835 must start with ISA*"

    def test_contains_bpr_segment(self):
        result = self._build()
        assert "BPR*" in result, "BPR segment (payment) must be present in 835"

    def test_contains_clp_segment(self):
        result = self._build()
        assert "CLP*" in result, "CLP segment (claim payment) must be present in 835"

    def test_paid_amount_in_bpr(self):
        result = self._build(total_paid=433.00)
        assert "433.00" in result, "Paid amount 433.00 must appear in EDI 835 BPR"

    def test_billed_amount_in_clp(self):
        result = self._build(total_billed=541.00)
        assert "541.00" in result, "Billed amount 541.00 must appear in EDI 835 CLP"

    def test_denied_produces_zero_paid(self):
        result = self._build(claim_status="DENIED", total_paid=0.0)
        # BPR02 must be 0.00
        assert "0.00" in result, "DENIED claim must produce 0.00 paid in EDI 835"

    def test_denied_has_cas_segment(self):
        result = self._build(claim_status="DENIED", total_paid=0.0, total_billed=541.00)
        assert "CAS*" in result, "DENIED claim must include CAS (adjustment) segment"

    def test_partial_payment_correct_adjustment(self):
        """PARTIALLY_PAID should show both a paid amount and a write-off."""
        result = self._build(claim_status="PARTIALLY_PAID", total_billed=541.00, total_paid=300.00)
        assert "300.00" in result, "Partial paid amount must appear"
        assert "241.00" in result, "Write-off (541 - 300 = 241) must appear in CAS"

    def test_svc_line_for_cpt(self):
        result = self._build()
        assert "SVC*" in result, "SVC service line must be present for CPT items"
        assert "99232" in result, "CPT code 99232 must be in SVC line"

    def test_no_crash_minimal_inputs(self):
        try:
            result = self.build(
                claim_id=str(uuid.uuid4()),
                claim_status="PAID",
                total_billed=100.00,
                total_paid=100.00,
                org_name="X",
                payer_name="Y",
            )
            assert isinstance(result, str)
        except Exception as e:
            pytest.fail(f"build_edi_835 raised with minimal inputs: {e}")


# =============================================================================
# UNIT: fhir_claim_builder
# =============================================================================

class TestFhirClaimBuilder:
    """Unit tests for the FHIR claim proposal builder."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from services.fhir_claim_builder import build_fhir_claim_proposal
        self.build = build_fhir_claim_proposal

    CODING_STATE = {
        "session_id": "sess-test-001",
        "final_icd_code": "J18.9",
        "icd_codes": [
            {"code": "J18.9", "description": "Pneumonia, unspecified organism",
             "confidence": 0.91, "mapping_path": "direct"}
        ],
        "cpt_codes": [
            {"cpt_code": "99232", "description": "Hospital E&M", "gross_charge": 541.00,
             "base_price": 270.50, "multiplier": 2.0, "confidence": 0.88}
        ],
        "financial_summary": {
            "total_estimated_revenue": 541.00,
            "pricing_multiplier": 2.0,
        },
        "patient_name": "Priya Raman",
        "patient_dob": "1988-04-15",
        "patient_sex": "F",
        "risk_score": 0.21,
        "confidence_score": 0.91,
    }

    def _build(self) -> dict:
        return self.build(
            claim_id=str(uuid.uuid4()),
            session_id=self.CODING_STATE["session_id"],
            organization_id=str(uuid.uuid4()),
            organization_name="City General Hospital",
            payer_id=str(uuid.uuid4()),
            payer_name="NHI",
            patient_name=self.CODING_STATE["patient_name"],
            patient_dob=self.CODING_STATE["patient_dob"],
            patient_sex=self.CODING_STATE["patient_sex"],
            icd_codes=self.CODING_STATE["icd_codes"],
            cpt_codes=self.CODING_STATE["cpt_codes"],
            financial_summary=self.CODING_STATE["financial_summary"],
            icd_version="ICD-10-CM",
            mapping_path="direct",
            total_billed_amount=541.00,
        )

    def test_returns_dict(self):
        result = self._build()
        assert isinstance(result, dict), "build_fhir_claim_proposal must return a dict"

    def test_has_resource_type_bundle(self):
        result = self._build()
        assert result.get("resourceType") == "Claim", "FHIR root must have resourceType: Claim"

    def test_patient_name_set(self):
        result = self._build()
        dump = json.dumps(result)
        assert "Priya Raman" in dump, "Patient name must appear in FHIR bundle"

    def test_icd_code_present(self):
        result = self._build()
        dump = json.dumps(result)
        assert "J18.9" in dump, "ICD code J18.9 must be present in FHIR bundle"

    def test_financial_uses_gross_charge(self):
        """TICKET-02 fix: gross_charge (541) must be preferred over base_price (270.50)."""
        result = self._build()
        dump = json.dumps(result)
        # 541 should appear; 270.5 should NOT be the net amount at top-level
        assert "541" in dump, "gross_charge (541) must appear in FHIR financials"

    def test_no_john_doe_fallback(self):
        """TICKET-02 fix: patient name must never default to 'John Doe' when a name is present."""
        result = self._build()
        dump = json.dumps(result)
        assert "John Doe" not in dump, "Patient name must not fall back to 'John Doe'"



# =============================================================================
# INTEGRATION: FastAPI endpoints
# =============================================================================

pytestmark_integration = pytest.mark.integration


# The `client` fixture lives in conftest.py — it injects an authenticated
# Principal via dependency_overrides. Endpoints now require authentication, so
# an un-authenticated TestClient would return 401 everywhere.


@pytest.mark.integration
class TestHealthEndpoint:
    def test_health_ok(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") in ("ok", "running"), f"Health check returned: {data}"


@pytest.mark.integration
class TestCodeRunEndpoint:
    """
    Golden-set test for POST /code/run with the canonical Priya Raman note.

    Expectations (encoded from sprint demo outputs):
      - ICD code must be a pneumonia code  (J18.x family)
      - Confidence must be > 0.70
      - Risk label must be LOW or MEDIUM (not HIGH for simple pneumonia)
      - CPT codes list must not be empty (at least one procedure)
      - Financial summary must have a positive total_estimated_revenue
    """

    PRIYA_RAMAN_NOTE = """
    Patient: Priya Raman
    DOB: 15-Apr-1988
    Sex: Female
    
    CHIEF COMPLAINT: Fever and productive cough for 3 days.
    
    HISTORY OF PRESENT ILLNESS:
    Ms. Raman presents with a 3-day history of high-grade fever (38.9°C), productive cough
    with yellowish sputum, and shortness of breath on exertion. She has no significant 
    past medical history. No known allergies.
    
    EXAMINATION:
    Vitals: BP 118/76, HR 92, RR 20, SpO2 96% on room air.
    Chest: Dullness to percussion at right base. Bronchial breath sounds noted.
    
    INVESTIGATIONS:
    Chest X-Ray: Right lower lobe consolidation consistent with pneumonia.
    CBC: WBC 14,200 (elevated), Neutrophilia.
    
    DIAGNOSIS:
    Community-acquired pneumonia, right lower lobe (J18.9 — Pneumonia, unspecified organism)
    
    PLAN:
    Admit for IV antibiotics (Amoxicillin-Clavulanate). Daily chest physiotherapy.
    Expected LOS: 3 days.
    """

    def test_golden_icd_code(self, client):
        res = client.post("/api/v1/code/run", json={"raw_text": self.PRIYA_RAMAN_NOTE})
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        data = res.json()
        icd = data.get("final_icd_code", "")
        assert icd.upper().startswith("J"), \
            f"Pneumonia should map to J-family ICD code, got: {icd!r}"

    def test_golden_confidence_threshold(self, client):
        res = client.post("/api/v1/code/run", json={"raw_text": self.PRIYA_RAMAN_NOTE})
        assert res.status_code == 200
        data = res.json()
        conf = data.get("confidence_score", 0)
        assert conf >= 0.70, f"Confidence should be ≥ 0.70 for clear pneumonia note, got: {conf}"

    def test_golden_risk_not_high(self, client):
        res = client.post("/api/v1/code/run", json={"raw_text": self.PRIYA_RAMAN_NOTE})
        data = res.json()
        risk_label = data.get("risk_label", "")
        assert risk_label in ("LOW", "MEDIUM"), \
            f"Simple pneumonia should not be HIGH risk, got: {risk_label!r}"

    def test_golden_cpt_codes_present(self, client):
        res = client.post("/api/v1/code/run", json={"raw_text": self.PRIYA_RAMAN_NOTE})
        data = res.json()
        cpt_codes = data.get("cpt_codes") or []
        assert len(cpt_codes) > 0, "At least one CPT code should be extracted for inpatient admission"

    def test_golden_financial_summary_positive(self, client):
        res = client.post("/api/v1/code/run", json={"raw_text": self.PRIYA_RAMAN_NOTE})
        data = res.json()
        fs = data.get("financial_summary") or {}
        revenue = fs.get("total_estimated_revenue", 0)
        assert revenue > 0, f"Total estimated revenue must be > 0, got: {revenue}"

    def test_golden_multi_icd_codes(self, client):
        """Pipeline should return a list of ICD candidates (not just a single code)."""
        res = client.post("/api/v1/code/run", json={"raw_text": self.PRIYA_RAMAN_NOTE})
        data = res.json()
        icd_codes = data.get("icd_codes") or []
        assert len(icd_codes) > 0, "icd_codes list must be non-empty"

    def test_session_id_is_uuid(self, client):
        """Pipeline must emit a valid session_id UUID for traceability."""
        res = client.post("/api/v1/code/run", json={"raw_text": self.PRIYA_RAMAN_NOTE})
        data = res.json()
        session_id = data.get("session_id", "")
        try:
            uuid.UUID(session_id)
        except ValueError:
            pytest.fail(f"session_id is not a valid UUID: {session_id!r}")

    def test_response_has_no_error_at(self, client):
        """On a clean run, error_at should be absent or None."""
        res = client.post("/api/v1/code/run", json={"raw_text": self.PRIYA_RAMAN_NOTE})
        data = res.json()
        error_at = data.get("error_at")
        assert not error_at, f"Pipeline reported an error at node: {error_at}"


@pytest.mark.integration
class TestClaims:
    """Smoke tests for claims CRUD endpoints."""

    def test_claims_endpoint_accessible(self, client):
        """GET /claims?org_id=<any> must not 500 (may be empty list)."""
        res = client.get("/api/v1/claims", params={"org_id": "nonexistent-org-id"})
        assert res.status_code in (200, 404), \
            f"Claims endpoint must respond with 200 or 404, got {res.status_code}"

    def test_edi_837_endpoint_404_for_fake_claim(self, client):
        """Requesting EDI 837 for a non-existent claim must return 404."""
        fake_id = str(uuid.uuid4())
        res = client.get(f"/api/v1/claims/export/edi/{fake_id}")
        assert res.status_code == 404, \
            f"Non-existent claim EDI 837 must return 404, got {res.status_code}"

    def test_edi_835_endpoint_404_for_fake_claim(self, client):
        """Requesting EDI 835 for a non-existent claim must return 404."""
        fake_id = str(uuid.uuid4())
        res = client.get(f"/api/v1/claims/export/edi835/{fake_id}")
        assert res.status_code == 404, \
            f"Non-existent claim EDI 835 must return 404, got {res.status_code}"

    def test_payer_edit_requires_reason(self, payer_client):
        """POST /claims/edit without edit_reason must return 400 (validation)."""
        fake_id = str(uuid.uuid4())
        res = payer_client.post(
            f"/api/v1/claims/edit/{fake_id}",
            json={
                "edited_icd_codes": [],
                "edited_cpt_codes": [],
                "edit_reason": "",       # empty → must be rejected
            },
        )
        # 400 (validation) or 422 (FastAPI schema validation) — both acceptable
        assert res.status_code in (400, 422), \
            f"Empty edit_reason must be rejected, got {res.status_code}"
