"""
Tests for server-side account provisioning (POST /api/v1/admin/users).

Admin screens used to create accounts in the browser with
supabase.auth.signUp() and then insert into public.users with an organisation
chosen by the browser. Disabling public signup — the only control that stops
strangers creating accounts, since the anon key ships in the frontend — broke
those screens. Provisioning now runs on the server through the Auth admin API.

Pinned here: only admins may call it; the organisation comes from the token and
cannot be supplied; roles must fit the organisation type; branches must belong
to the caller's organisation; and no account is ever left half-created.
"""
import asyncio

import httpx
import pytest

pytestmark = pytest.mark.usefixtures("fake_db")

AUTH_ID = "9d7b1d4e-5f2a-4c3b-8e1d-0a1b2c3d4e5f"
BRANCH_ID = "11111111-2222-4333-8444-555555555555"


@pytest.fixture
def provisioning(monkeypatch):
    """Substitute the Auth admin client; record what the route asked it to do."""
    import routes.admin as admin

    record = {"created": [], "deleted": [], "fail": None}

    async def fake_create(email, password, full_name):
        if record["fail"] is not None:
            raise record["fail"]
        record["created"].append(email)
        return AUTH_ID

    async def fake_delete(auth_id):
        record["deleted"].append(auth_id)

    monkeypatch.setattr(admin, "create_auth_user", fake_create)
    monkeypatch.setattr(admin, "delete_auth_user", fake_delete)
    return record


def _body(**overrides) -> dict:
    body = {
        "email": "new.coder@hospital.test",
        "full_name": "New Coder",
        "password": "correct-horse-battery",
        "role": "coder",
    }
    body.update(overrides)
    return body


def _user_rows(fake_db) -> list[dict]:
    return [c[2] for c in fake_db.calls if c[0] == "insert" and c[1] == "users"]


class TestCreatesAccountsInTheCallersOrganisation:
    def test_hospital_admin_creates_a_coder(self, client, fake_db, provisioning, hospital_principal):
        res = client.post("/api/v1/admin/users", json=_body())
        assert res.status_code == 201, res.text
        assert provisioning["created"] == ["new.coder@hospital.test"]

        row = _user_rows(fake_db)[0]
        assert row["organization_id"] == hospital_principal.organization_id
        assert row["auth_id"] == AUTH_ID
        assert row["role"] == "coder"

    def test_payer_admin_creates_a_claims_reviewer(self, payer_client, fake_db, provisioning, payer_principal):
        res = payer_client.post("/api/v1/admin/users", json=_body(role="payer"))
        assert res.status_code == 201, res.text
        assert _user_rows(fake_db)[0]["organization_id"] == payer_principal.organization_id

    def test_password_is_never_echoed_or_stored_in_the_app_table(self, client, fake_db, provisioning):
        res = client.post("/api/v1/admin/users", json=_body())
        assert "correct-horse-battery" not in res.text
        assert "password" not in _user_rows(fake_db)[0]

    def test_email_is_normalised(self, client, fake_db, provisioning):
        res = client.post("/api/v1/admin/users", json=_body(email="  New.Coder@Hospital.TEST "))
        assert res.status_code == 201, res.text
        assert provisioning["created"] == ["new.coder@hospital.test"]


class TestTenantBoundary:
    def test_organisation_cannot_be_supplied_in_the_body(self, client, provisioning):
        res = client.post("/api/v1/admin/users",
                          json=_body(organization_id="99999999-9999-9999-9999-999999999999"))
        assert res.status_code == 422
        assert provisioning["created"] == [], "no account may be created for a rejected request"

    def test_branch_from_another_organisation_is_rejected(self, client, fake_db, provisioning, hospital_principal):
        fake_db.on("select_one", None)
        res = client.post("/api/v1/admin/users", json=_body(branch_id=BRANCH_ID))
        assert res.status_code == 422
        assert provisioning["created"] == []
        assert fake_db.filters_for("select_one", "branches") == {
            "id": f"eq.{BRANCH_ID}",
            "organization_id": f"eq.{hospital_principal.organization_id}",
        }

    def test_branch_in_own_organisation_is_accepted(self, client, fake_db, provisioning):
        fake_db.on("select_one", {"id": BRANCH_ID})
        res = client.post("/api/v1/admin/users", json=_body(branch_id=BRANCH_ID))
        assert res.status_code == 201, res.text
        assert _user_rows(fake_db)[0]["branch_id"] == BRANCH_ID


class TestRolesFitTheOrganisation:
    def test_hospital_cannot_create_a_payer_reviewer(self, client, provisioning):
        res = client.post("/api/v1/admin/users", json=_body(role="payer"))
        assert res.status_code == 422
        assert provisioning["created"] == []

    @pytest.mark.parametrize("role", ["coder", "rcm", "auditor"])
    def test_payer_cannot_create_hospital_roles(self, payer_client, provisioning, role):
        res = payer_client.post("/api/v1/admin/users", json=_body(role=role))
        assert res.status_code == 422
        assert provisioning["created"] == []

    def test_payer_organisations_have_no_branches(self, payer_client, provisioning):
        res = payer_client.post("/api/v1/admin/users", json=_body(role="payer", branch_id=BRANCH_ID))
        assert res.status_code == 422


class TestAccessControl:
    def test_non_admins_are_refused(self, hospital_principal, provisioning):
        from fastapi.testclient import TestClient

        import main
        from auth import Principal, get_principal

        coder = Principal(
            auth_id="test-auth-coder", user_id="test-user-coder", email="coder@test.local",
            organization_id=hospital_principal.organization_id, role="coder",
            org_type="hospital", token="test-token",
        )
        main.app.dependency_overrides[get_principal] = lambda: coder
        try:
            res = TestClient(main.app).post("/api/v1/admin/users", json=_body())
        finally:
            main.app.dependency_overrides.clear()
        assert res.status_code == 403
        assert provisioning["created"] == []

    def test_anonymous_callers_are_rejected(self, anon_client, provisioning):
        assert anon_client.post("/api/v1/admin/users", json=_body()).status_code == 401
        assert provisioning["created"] == []


class TestValidation:
    @pytest.mark.parametrize("field,value", [
        ("password", "short"),
        ("full_name", "   "),
        ("role", "superuser"),
        ("email", "not-an-email"),
    ])
    def test_invalid_input_is_rejected_before_any_account_exists(self, client, provisioning, field, value):
        res = client.post("/api/v1/admin/users", json=_body(**{field: value}))
        assert res.status_code == 422
        assert provisioning["created"] == []


class TestNeverHalfCreated:
    def test_existing_email_conflicts_before_an_account_is_created(self, client, fake_db, provisioning):
        fake_db.on("select", [{"id": "existing-user"}])
        res = client.post("/api/v1/admin/users", json=_body())
        assert res.status_code == 409
        assert provisioning["created"] == []

    def test_duplicate_reported_by_the_auth_service_is_a_conflict(self, client, provisioning):
        from services.user_provisioning import EmailAlreadyRegistered

        provisioning["fail"] = EmailAlreadyRegistered("taken", status=422)
        assert client.post("/api/v1/admin/users", json=_body()).status_code == 409

    def test_auth_service_failure_is_502_without_internal_detail(self, client, provisioning):
        from services.user_provisioning import ProvisioningError

        provisioning["fail"] = ProvisioningError("auth admin API returned 500", status=500)
        res = client.post("/api/v1/admin/users", json=_body())
        assert res.status_code == 502
        assert "auth admin" not in res.text

    def test_app_profile_failure_removes_the_auth_account(self, client, fake_db, provisioning):
        fake_db.on("insert", RuntimeError("database unavailable"))
        res = client.post("/api/v1/admin/users", json=_body())
        assert res.status_code == 500
        assert provisioning["deleted"] == [AUTH_ID], "an orphaned login must be removed"


class TestAuthAdminClient:
    """The HTTP contract with Supabase's Auth admin API, via a mock transport."""

    @pytest.fixture
    def transport(self, monkeypatch):
        import services.user_provisioning as up
        from config import settings

        monkeypatch.setattr(settings, "supabase_service_key", "service-key-for-tests")
        captured: dict = {}
        state = {"status": 200, "json": {"id": AUTH_ID}}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(state["status"], json=state["json"])

        monkeypatch.setattr(up, "_http_client",
                            lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        return captured, state

    def test_create_uses_the_service_role_and_confirms_the_email(self, transport):
        import json

        from services.user_provisioning import create_auth_user

        captured, _ = transport
        assert asyncio.run(create_auth_user("a@b.test", "correct-horse", "A B")) == AUTH_ID
        request = captured["request"]
        assert request.url.path.endswith("/auth/v1/admin/users")
        assert request.headers["Authorization"] == "Bearer service-key-for-tests"
        payload = json.loads(request.content)
        assert payload["email_confirm"] is True
        assert payload["user_metadata"] == {"full_name": "A B"}

    def test_duplicate_email_is_recognised(self, transport):
        from services.user_provisioning import EmailAlreadyRegistered, create_auth_user

        _, state = transport
        state.update(status=422, json={"error_code": "email_exists", "msg": "already registered"})
        with pytest.raises(EmailAlreadyRegistered):
            asyncio.run(create_auth_user("a@b.test", "correct-horse", "A B"))

    def test_other_failures_raise_provisioning_error(self, transport):
        from services.user_provisioning import EmailAlreadyRegistered, ProvisioningError, create_auth_user

        _, state = transport
        state.update(status=500, json={"msg": "boom"})
        with pytest.raises(ProvisioningError) as exc:
            asyncio.run(create_auth_user("a@b.test", "correct-horse", "A B"))
        assert not isinstance(exc.value, EmailAlreadyRegistered)

    def test_missing_service_key_fails_before_any_request(self, monkeypatch):
        from config import settings
        from services.user_provisioning import ProvisioningError, create_auth_user

        monkeypatch.setattr(settings, "supabase_service_key", "")
        with pytest.raises(ProvisioningError):
            asyncio.run(create_auth_user("a@b.test", "correct-horse", "A B"))

    def test_deleting_an_already_missing_account_is_not_an_error(self, transport):
        from services.user_provisioning import delete_auth_user

        _, state = transport
        state.update(status=404, json={"msg": "not found"})
        asyncio.run(delete_auth_user(AUTH_ID))
