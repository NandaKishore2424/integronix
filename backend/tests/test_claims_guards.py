"""
Route-level tests for the claim submission and adjudication guards.

These run with NO database. Day 2 consolidated every data access onto
database.py — select / select_one / insert / update / rpc — which left a
single seam to substitute, so the full route logic (tenant checks, fail-closed
guards, optimistic locks, compensation on audit failure) is exercised in
milliseconds without Supabase.

What is asserted here is not just the status code but the SHAPE OF THE QUERY
the route issued: an optimistic lock is only a lock if the status predicate is
actually in the filters, and that is invisible from the response alone.
"""

import pytest

pytestmark = pytest.mark.usefixtures("fake_db")


COMPLETE_CASE = {
    "case_id": "11111111-1111-1111-1111-111111111111",
    "processing_status": "COMPLETE",
    "organization_id": "00000000-0000-0000-0000-000000000001",
}
GOOD_RESULT = {"ai_icd_code": "J18.9", "confidence_score": 0.82}


def _submission(**overrides) -> dict:
    body = {
        "session_id": "22222222-2222-2222-2222-222222222222",
        "organization_id": "00000000-0000-0000-0000-000000000001",
        "payer_id": "33333333-3333-3333-3333-333333333333",
        "patient_name": "Priya Raman",
        "patient_dob": "1988-04-15",
        "patient_sex": "F",
        "total_billed_amount": 27.53,
        "claim_data": {
            "confidence_score": 0.82,
            "risk_score": 0.1,
            "mapping_path": "embedding",
            "cpt_codes": [{"code": "71045", "base_price": 27.53}],
            "financial_summary": {
                "total_estimated_revenue": 27.53,
                "line_items": [{"code": "71045", "base_price": 27.53}],
            },
        },
    }
    body.update(overrides)
    return body


class TestSubmissionFailsClosed:
    """A run that did not produce a usable code must never become a claim."""

    def test_rejects_when_no_coded_session_exists(self, client, fake_db):
        fake_db.on("select", []).on("select_one", None)
        res = client.post("/api/v1/claims/submit", json=_submission())
        assert res.status_code == 422
        assert "Run the coding pipeline first" in res.json()["detail"]

    def test_rejects_a_failed_pipeline_run(self, client, fake_db):
        fake_db.on("select", []).on("select_one", {**COMPLETE_CASE, "processing_status": "FAILED"})
        res = client.post("/api/v1/claims/submit", json=_submission())
        assert res.status_code == 422
        assert "did not complete successfully" in res.json()["detail"]

    def test_rejects_an_unknown_code(self, client, fake_db):
        fake_db.on("select", []).on(
            "select_one", COMPLETE_CASE, {"ai_icd_code": "UNKNOWN", "confidence_score": 0.0}
        )
        res = client.post("/api/v1/claims/submit", json=_submission())
        assert res.status_code == 422
        assert "no usable code" in res.json()["detail"]

    def test_rejects_zero_confidence(self, client, fake_db):
        fake_db.on("select", []).on(
            "select_one", COMPLETE_CASE, {"ai_icd_code": "J18.9", "confidence_score": 0.0}
        )
        res = client.post("/api/v1/claims/submit", json=_submission())
        assert res.status_code == 422


class TestDoubleBillingGuard:
    def test_second_submission_for_a_session_is_rejected(self, client, fake_db):
        fake_db.on("select", [{"id": "existing-claim"}])
        res = client.post("/api/v1/claims/submit", json=_submission())
        assert res.status_code == 400
        assert "already been submitted" in res.json()["detail"]

    def test_duplicate_rejection_is_not_swallowed(self, client, fake_db):
        """
        Regression: the guard raised HTTPException inside `try/except
        Exception: pass`. HTTPException IS an Exception, so the rejection it
        raised was swallowed by its own handler and the claim went through.
        """
        fake_db.on("select", [{"id": "existing-claim"}])
        res = client.post("/api/v1/claims/submit", json=_submission())
        assert res.status_code != 200


class TestTenantIsolation:
    def test_cannot_submit_against_another_orgs_session(self, client, fake_db):
        """The session exists, but belongs to a different hospital."""
        fake_db.on("select", []).on(
            "select_one",
            {**COMPLETE_CASE, "organization_id": "99999999-9999-9999-9999-999999999999"},
        )
        res = client.post("/api/v1/claims/submit", json=_submission())
        assert res.status_code == 403
        assert "does not belong to your organization" in res.json()["detail"]

    def test_body_organization_id_cannot_override_the_token(self, client):
        """
        assert_org rejects a body org that disagrees with the verified token,
        so a client cannot bill as another tenant by editing the payload.
        """
        res = client.post("/api/v1/claims/submit", json=_submission(
            organization_id="99999999-9999-9999-9999-999999999999"))
        assert res.status_code == 403

    def test_claim_row_records_the_verified_org(self, client, fake_db):
        fake_db.on("select", []).on("select_one", COMPLETE_CASE, GOOD_RESULT, None, None)
        client.post("/api/v1/claims/submit", json=_submission())
        inserts = [c for c in fake_db.calls if c[0] == "insert" and c[1] == "claims"]
        assert inserts, "a claim insert should have been attempted"
        assert inserts[0][2]["organization_id"] == "00000000-0000-0000-0000-000000000001"


class TestAuditTrailIsMandatory:
    def test_claim_is_withdrawn_when_the_audit_write_fails(self, client, fake_db):
        """
        HIPAA: a claim with no audit row must not be a representable state. If
        the audit insert fails, the claim is DELETED and the request errors,
        rather than leaving an untracked claim in the payer queue.

        Deletion, not a status change: claims.status has a CHECK constraint
        listing the valid states, so the original "SUBMISSION_FAILED" marker
        was itself rejected — the compensation failed, and the orphaned
        SUBMITTED claim then tripped the duplicate guard and blocked retry for
        that session permanently. See tests/test_schema_contract.py.
        """
        fake_db.on("select", []).on("select_one", COMPLETE_CASE, GOOD_RESULT, None, None)
        fake_db.on("insert",
                   {"id": "44444444-4444-4444-4444-444444444444"},   # the claim
                   RuntimeError("audit table unavailable"))          # the audit row

        res = client.post("/api/v1/claims/submit", json=_submission())
        assert res.status_code == 500
        assert "audit trail" in res.json()["detail"]

        deletes = [c for c in fake_db.calls if c[0] == "delete" and c[1] == "claims"]
        assert deletes, "the orphaned claim must be removed"
        assert deletes[0][2] == {"id": "eq.44444444-4444-4444-4444-444444444444"}

    def test_audit_row_records_the_auth_id_not_the_app_user_id(self, client, fake_db):
        """
        claim_audit_logs.changed_by_user_id has a foreign key to auth.users,
        so it must carry Principal.auth_id. Passing Principal.user_id (the
        public.users row id) is a valid uuid that looks right in every mocked
        test and fails only against the real database.

        The fixture principal's auth_id is not a uuid, so it coerces to None —
        what matters here is that user_id never reaches the column.
        """
        fake_db.on("select", []).on("select_one", COMPLETE_CASE, GOOD_RESULT, None, None)
        client.post("/api/v1/claims/submit", json=_submission())

        audits = [c for c in fake_db.calls if c[0] == "insert" and c[1] == "claim_audit_logs"]
        assert audits, "an audit row should have been attempted"
        assert audits[0][2]["changed_by_user_id"] != "test-user-hospital"

    def test_successful_submission_writes_an_audit_row(self, client, fake_db):
        fake_db.on("select", []).on("select_one", COMPLETE_CASE, GOOD_RESULT, None, None)
        res = client.post("/api/v1/claims/submit", json=_submission())
        assert res.status_code == 200
        audits = [c for c in fake_db.calls if c[0] == "insert" and c[1] == "claim_audit_logs"]
        assert len(audits) == 1


class TestAdjudicationConcurrency:
    """
    The write goes through the adjudicate_claim SQL function so the status
    check rides inside the UPDATE as an optimistic lock. These assert the
    route honours the function's verdict.
    """

    SUBMITTED_CLAIM = {
        "id": "55555555-5555-5555-5555-555555555555",
        "status": "SUBMITTED",
        "organization_id": "00000000-0000-0000-0000-000000000001",
        "payer_id": "33333333-3333-3333-3333-333333333333",
        "total_billed_amount": 100.0,
        "claim_data": {"financial_summary": {"line_items": [{"base_price": 100.0}]}},
        "payers": {"base_allowed_multiplier": 1.0},
    }

    def _approve(self, payer_client):
        return payer_client.post(
            f"/api/v1/claims/adjudicate/{self.SUBMITTED_CLAIM['id']}",
            json={"action": "APPROVE", "payer_responsibility_pct": 0.8},
        )

    def test_losing_a_race_returns_409_not_a_second_payment(self, payer_client, fake_db):
        fake_db.on("select_one", self.SUBMITTED_CLAIM)
        fake_db.on("select", [{"id": "33333333-3333-3333-3333-333333333333"}])
        fake_db.on("rpc", {"ok": False, "reason": "status_conflict", "current_status": "PAID"})

        res = self._approve(payer_client)
        assert res.status_code == 409
        assert "modified concurrently" in res.json()["detail"]

    def test_missing_claim_surfaces_as_404(self, payer_client, fake_db):
        fake_db.on("select_one", self.SUBMITTED_CLAIM)
        fake_db.on("select", [{"id": "33333333-3333-3333-3333-333333333333"}])
        fake_db.on("rpc", {"ok": False, "reason": "not_found", "current_status": None})

        res = self._approve(payer_client)
        assert res.status_code == 404

    def test_already_adjudicated_claim_is_refused_before_any_write(self, payer_client, fake_db):
        fake_db.on("select_one", {**self.SUBMITTED_CLAIM, "status": "PAID"})
        fake_db.on("select", [{"id": "33333333-3333-3333-3333-333333333333"}])

        res = self._approve(payer_client)
        assert res.status_code == 400
        assert not [c for c in fake_db.calls if c[0] == "rpc"], "must not attempt a write"

    def test_expected_status_is_sent_as_the_lock(self, payer_client, fake_db):
        """
        The lock only exists if the route tells the function which status it
        read. Without p_expected_status the UPDATE would match unconditionally.
        """
        fake_db.on("select_one", self.SUBMITTED_CLAIM)
        fake_db.on("select", [{"id": "33333333-3333-3333-3333-333333333333"}])
        fake_db.on("rpc", {"ok": True, "previous_status": "SUBMITTED", "new_status": "PARTIALLY_PAID"})

        res = self._approve(payer_client)
        assert res.status_code == 200
        rpc_call = next(c for c in fake_db.calls if c[0] == "rpc")
        assert rpc_call[1] == "adjudicate_claim"
        assert rpc_call[2]["p_expected_status"] == "SUBMITTED"

    def test_amounts_reconcile_in_the_response(self, payer_client, fake_db):
        fake_db.on("select_one", self.SUBMITTED_CLAIM)
        fake_db.on("select", [{"id": "33333333-3333-3333-3333-333333333333"}])
        fake_db.on("rpc", {"ok": True, "previous_status": "SUBMITTED", "new_status": "PARTIALLY_PAID"})

        details = self._approve(payer_client).json()["adjudication_details"]
        assert details["total_paid_amount"] + details["patient_responsibility"] == \
            details["total_allowed_amount"]

    def test_payer_cannot_allow_more_than_was_billed(self, payer_client, fake_db):
        """A generous contract multiplier must not pay above the billed amount."""
        claim = {**self.SUBMITTED_CLAIM, "payers": {"base_allowed_multiplier": 5.0}}
        fake_db.on("select_one", claim)
        fake_db.on("select", [{"id": "33333333-3333-3333-3333-333333333333"}])
        fake_db.on("rpc", {"ok": True, "previous_status": "SUBMITTED", "new_status": "PAID"})

        details = self._approve(payer_client).json()["adjudication_details"]
        assert details["total_allowed_amount"] <= 100.0


class TestAdjudicationAuthorisation:
    def test_hospital_user_cannot_adjudicate(self, client):
        res = client.post(
            "/api/v1/claims/adjudicate/55555555-5555-5555-5555-555555555555",
            json={"action": "APPROVE", "payer_responsibility_pct": 0.8},
        )
        assert res.status_code == 403

    @pytest.mark.parametrize("pct", [-0.1, 1.5, 5.0])
    def test_payer_responsibility_is_bounded(self, payer_client, pct):
        """
        Unbounded, 5.0 paid five times the allowed amount and left patient
        responsibility negative.
        """
        res = payer_client.post(
            "/api/v1/claims/adjudicate/55555555-5555-5555-5555-555555555555",
            json={"action": "APPROVE", "payer_responsibility_pct": pct},
        )
        assert res.status_code == 422

    def test_action_must_be_approve_or_deny(self, payer_client):
        res = payer_client.post(
            "/api/v1/claims/adjudicate/55555555-5555-5555-5555-555555555555",
            json={"action": "TRANSFER_FUNDS", "payer_responsibility_pct": 0.8},
        )
        assert res.status_code == 422
