"""
Unit tests for the tenant and role boundary in auth.py.

Context: before this layer existed, all 27 endpoints were unauthenticated, and
the only thing separating one hospital's patients from another's was the
organization_id the caller happened to put in the URL. Principal is where that
is now decided, so its behaviour is pinned here rather than left to the
integration suite (which is skipped whenever credentials are absent — i.e. in
CI, which is exactly where a regression would slip through).
"""

import pytest
from fastapi import HTTPException

from auth import Principal

ORG_A = "00000000-0000-0000-0000-00000000000a"
ORG_B = "00000000-0000-0000-0000-00000000000b"


def _principal(**overrides) -> Principal:
    fields = {
        "auth_id": "auth-1",
        "user_id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
        "email": "coder@hospital.test",
        "organization_id": ORG_A,
        "role": "coder",
        "org_type": "hospital",
        "token": "token",
    }
    fields.update(overrides)
    return Principal(**fields)


class TestTenantBoundary:
    def test_own_org_is_allowed(self):
        assert _principal().assert_org(ORG_A) == ORG_A

    def test_another_org_is_refused(self):
        with pytest.raises(HTTPException) as exc:
            _principal().assert_org(ORG_B)
        assert exc.value.status_code == 403

    def test_none_means_use_mine(self):
        """
        Passing None is "scope me to my own org", which is always allowed —
        this is what lets routes drop the client-supplied id entirely.
        """
        assert _principal().assert_org(None) == ORG_A

    def test_returns_the_callers_org_not_the_argument(self):
        """
        The return value is the caller's OWN org, so routes thread that
        onward and never carry a request-supplied value into a query. The
        check is worthless if the unchecked value is what gets used.
        """
        result = _principal().assert_org(ORG_A)
        assert result == _principal().organization_id

    def test_result_is_a_string_for_query_building(self):
        assert isinstance(_principal().assert_org(None), str)

    @pytest.mark.parametrize("supplied", [
        "00000000-0000-0000-0000-00000000000B",   # case-flipped
        " 00000000-0000-0000-0000-00000000000a",  # leading space
        "00000000-0000-0000-0000-00000000000a ",  # trailing space
    ])
    def test_near_miss_org_ids_do_not_slip_through(self, supplied):
        """Anything that is not an exact match is refused, not normalised."""
        with pytest.raises(HTTPException) as exc:
            _principal().assert_org(supplied)
        assert exc.value.status_code == 403


class TestRoleBoundary:
    def test_permitted_role_passes(self):
        _principal(role="coder").assert_role("coder", "rcm", "admin")

    def test_other_roles_are_refused(self):
        with pytest.raises(HTTPException) as exc:
            _principal(role="auditor").assert_role("coder", "rcm", "admin")
        assert exc.value.status_code == 403

    def test_empty_allowlist_refuses_everyone(self):
        """Fail closed: naming no roles must not mean "anyone"."""
        with pytest.raises(HTTPException):
            _principal(role="admin").assert_role()

    def test_role_matching_is_exact(self):
        with pytest.raises(HTTPException):
            _principal(role="Admin").assert_role("admin")


class TestOrgType:
    def test_payer_org_is_recognised(self):
        assert _principal(org_type="insurance_payer").is_payer is True

    def test_hospital_is_not_a_payer(self):
        assert _principal(org_type="hospital").is_payer is False

    @pytest.mark.parametrize("org_type", ["", None, "unknown", "clinic"])
    def test_unrecognised_org_types_are_not_payers(self, org_type):
        """
        is_payer gates adjudication — the ability to approve payments. An
        unfamiliar or missing org_type must never grant it.
        """
        assert _principal(org_type=org_type).is_payer is False
