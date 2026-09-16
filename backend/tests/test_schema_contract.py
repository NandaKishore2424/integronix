"""
Schema-contract tests — the assumptions the code makes about the database.

WHY THIS FILE EXISTS

Every unit test in this suite runs against a fake data layer. That fake
returns whatever a test queues; it enforces no foreign keys, no CHECK
constraints and no column types. So a route can be completely correct in its
logic and still fail on contact with Postgres, and 209 green tests will not
say a word about it.

Exactly that happened. Claim submission wrote
`claim_audit_logs.changed_by_user_id = principal.user_id`, which is a valid
uuid and looked right in every mocked test. But that column has a foreign key
to **auth.users**, while `user_id` is a **public.users** row id. The insert
failed with a foreign-key violation, the compensation path then tried to set
`claims.status = 'SUBMISSION_FAILED'` — a value the status CHECK constraint
does not permit — and the claim was left orphaned in SUBMITTED, permanently
blocking retry for that session.

These tests assert the schema facts the code depends on. They are integration
tests because there is no way to check a constraint without a database, and
that is the point: this is the layer mocks cannot cover.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def db():
    import os

    import psycopg2

    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    conn = psycopg2.connect(url, connect_timeout=20)
    yield conn
    conn.close()


def _fk_target(db, table: str, column: str) -> str | None:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT tgt_ns.nspname || '.' || tgt.relname
              FROM pg_constraint con
              JOIN pg_class src        ON src.oid = con.conrelid
              JOIN pg_class tgt        ON tgt.oid = con.confrelid
              JOIN pg_namespace tgt_ns ON tgt_ns.oid = tgt.relnamespace
              JOIN pg_attribute att
                ON att.attrelid = src.oid AND att.attnum = ANY (con.conkey)
             WHERE src.relname = %s AND att.attname = %s AND con.contype = 'f'
            """,
            (table, column),
        )
        row = cur.fetchone()
        return row[0] if row else None


def _check_constraint(db, table: str, name: str) -> str | None:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(con.oid)
              FROM pg_constraint con
              JOIN pg_class c ON c.oid = con.conrelid
             WHERE c.relname = %s AND con.conname = %s AND con.contype = 'c'
            """,
            (table, name),
        )
        row = cur.fetchone()
        return row[0] if row else None


class TestAuditLogForeignKeys:
    def test_changed_by_user_id_points_at_auth_users(self, db):
        """
        The code must send Principal.auth_id here, not Principal.user_id.
        If this FK is ever repointed at public.users, routes/claims.py must
        change in the same commit — and this test is what forces that.
        """
        assert _fk_target(db, "claim_audit_logs", "changed_by_user_id") == "auth.users"

    def test_claim_id_points_at_claims(self, db):
        assert _fk_target(db, "claim_audit_logs", "claim_id") == "public.claims"


class TestClaimStatusValues:
    """
    Every status string the code writes must be permitted by the CHECK
    constraint. A status the constraint rejects fails at write time — and if
    it is written on an error path, the failure lands precisely when things
    are already going wrong.
    """

    # Everything routes/claims.py and migration 021 can set.
    STATUSES_THE_CODE_WRITES = {
        "SUBMITTED", "PAID", "PARTIALLY_PAID", "DENIED", "APPEALED",
    }

    def test_every_status_the_code_writes_is_allowed(self, db):
        definition = _check_constraint(db, "claims", "claims_status_check")
        assert definition, "claims_status_check constraint is missing"
        for status in self.STATUSES_THE_CODE_WRITES:
            assert f"'{status}'" in definition, (
                f"code writes claims.status = {status!r}, which the CHECK "
                f"constraint does not permit: {definition}"
            )

    def test_submission_failed_is_not_a_valid_status(self, db):
        """
        Regression: the audit-failure compensation set this. It is not in the
        constraint, so the compensation itself failed and left an orphaned
        SUBMITTED claim that blocked retry forever. The path now deletes the
        claim instead. If someone adds SUBMISSION_FAILED to the schema later,
        this test fails and the compensation can be reconsidered deliberately.
        """
        definition = _check_constraint(db, "claims", "claims_status_check")
        assert "SUBMISSION_FAILED" not in definition


class TestColumnsTheCodeWrites:
    @pytest.mark.parametrize("table,column", [
        ("clinical_cases", "organization_id"),
        ("coding_results", "organization_id"),
        ("claims", "organization_id"),
        ("claims", "adjudicated_at"),
        ("claim_audit_logs", "changed_by_user_id"),
        ("payers", "organization_id"),
    ])
    def test_column_exists(self, db, table, column):
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM information_schema.columns
                 WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
                """,
                (table, column),
            )
            assert cur.fetchone(), f"{table}.{column} is written by the code but does not exist"


class TestAtomicAdjudicationFunctions:
    """Migration 021 must be applied, or adjudication silently falls back."""

    @pytest.mark.parametrize("fn", ["adjudicate_claim", "change_claim_status"])
    def test_function_exists(self, db, fn):
        with db.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_proc WHERE proname = %s", (fn,))
            assert cur.fetchone(), f"{fn}() missing — apply migrations/schema/021"


class TestPayerOwnership:
    def test_no_payer_is_orphaned(self, db):
        """
        A payer with a NULL organization_id is invisible to every user: claims
        routed to it cannot be adjudicated by anyone, with no error raised.
        """
        with db.cursor() as cur:
            cur.execute("SELECT name FROM public.payers WHERE organization_id IS NULL")
            orphans = [r[0] for r in cur.fetchall()]
        assert not orphans, (
            f"payers with no owning organization: {orphans} — claims routed to "
            "them are invisible to every payer user. Run seeds/005."
        )


class TestUserProvisioningSchema:
    """Database facts POST /api/v1/admin/users depends on."""

    def test_users_auth_id_references_auth_users(self, db):
        assert _fk_target(db, "users", "auth_id") == "auth.users"

    def test_every_role_the_admin_api_can_assign_is_permitted(self, db):
        from routes.admin import HOSPITAL_ROLES, PAYER_ROLES

        definition = _check_constraint(db, "users", "users_role_check")
        assert definition, "users_role_check constraint is missing"
        for role in sorted(HOSPITAL_ROLES | PAYER_ROLES):
            assert f"'{role}'" in definition, (
                f"the admin API can assign {role!r}, which the constraint rejects"
            )

    def test_branches_belong_to_an_organisation(self, db):
        assert _fk_target(db, "branches", "organization_id") == "public.organizations"


class TestEveryReferencedObjectExists:
    """
    Regression: agents/audit_comparison.py read an `icd_evidence` table that no
    migration ever created. The fake data layer answers any table name, so the
    whole suite stayed green while every real run with a human code failed with
    a 404. These tests read the source for every table and RPC it names and
    check each one against the live schema.
    """

    BACKEND = Path(__file__).resolve().parents[1]
    FRONTEND_SRC = BACKEND.parent / "frontend" / "src"
    NAME = r"[\"']([a-z_][a-z0-9_]*)[\"']"
    TABLE_PATTERNS = [
        re.compile(r"\b(?:select|select_one|select_as_service|select_paginated|select_count"
                   r"|insert|update|upsert|delete)\(\s*(?:table\s*=\s*)?" + NAME),
        re.compile(r"\bselect_for\(\s*[A-Za-z_][\w.]*\s*,\s*(?:table\s*=\s*)?" + NAME),
        re.compile(r"\btable\s*=\s*" + NAME),
        re.compile(r"\.table\(\s*" + NAME),
    ]
    RPC_PATTERN = re.compile(r"\brpc\(\s*(?:function_name\s*=\s*)?" + NAME)
    BROWSER_PATTERN = re.compile(r"\.from\(\s*" + NAME + r"\s*\)")

    def _backend_sources(self):
        skip = {"venv", ".venv", "tests", "__pycache__"}
        for path in self.BACKEND.rglob("*.py"):
            if not skip.intersection(path.relative_to(self.BACKEND).parts):
                yield path, path.read_text()

    def _found(self, patterns, sources):
        names: dict[str, set[str]] = {}
        for path, text in sources:
            for pattern in patterns:
                for match in pattern.finditer(text):
                    names.setdefault(match.group(1), set()).add(path.name)
        return names

    def test_every_table_the_backend_names_exists(self, db):
        tables = self._found(self.TABLE_PATTERNS, self._backend_sources())
        assert "icd_codes" in tables, "the source scan found nothing; the patterns are broken"
        with db.cursor() as cur:
            missing = {}
            for name, files in tables.items():
                cur.execute("SELECT to_regclass(%s)", (f"public.{name}",))
                if cur.fetchone()[0] is None:
                    missing[name] = sorted(files)
        assert not missing, f"code references tables that do not exist: {missing}"

    def test_every_rpc_the_backend_calls_exists(self, db):
        functions = self._found([self.RPC_PATTERN], self._backend_sources())
        assert "match_icd_codes" in functions, "the source scan found nothing; the pattern is broken"
        with db.cursor() as cur:
            missing = {}
            for name, files in functions.items():
                cur.execute(
                    "SELECT 1 FROM pg_proc WHERE proname = %s AND pronamespace = 'public'::regnamespace",
                    (name,),
                )
                if cur.fetchone() is None:
                    missing[name] = sorted(files)
        assert not missing, f"code calls functions that do not exist: {missing}"

    def test_every_table_the_browser_reads_is_readable_by_signed_in_users(self, db):
        """supabase-js runs as `authenticated`; migration 022 grants only what it needs."""
        if not self.FRONTEND_SRC.is_dir():
            pytest.skip("frontend source not present")
        sources = ((p, p.read_text()) for p in self.FRONTEND_SRC.rglob("*.ts*"))
        tables = self._found([self.BROWSER_PATTERN], sources)
        assert tables, "the source scan found no supabase-js table reads"
        with db.cursor() as cur:
            unreadable = {}
            for name, files in tables.items():
                cur.execute("SELECT to_regclass(%s)", (f"public.{name}",))
                oid = cur.fetchone()[0]
                if oid is None:
                    unreadable[name] = "missing"
                    continue
                cur.execute("SELECT has_table_privilege('authenticated', %s::regclass, 'SELECT')", (f"public.{name}",))
                if not cur.fetchone()[0]:
                    unreadable[name] = sorted(files)
        assert not unreadable, f"the browser reads tables it cannot access: {unreadable}"


class TestLeastPrivilegeApiAccess:
    """Migration 022: deny by default through the public Data API."""

    def test_every_table_has_row_level_security(self, db):
        with db.cursor() as cur:
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND NOT rowsecurity")
            assert cur.fetchall() == []

    def test_anon_has_no_table_privileges(self, db):
        with db.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT table_name FROM information_schema.role_table_grants "
                "WHERE table_schema = 'public' AND grantee = 'anon'"
            )
            assert cur.fetchall() == []

    def test_backend_role_can_use_every_table(self, db):
        with db.cursor() as cur:
            cur.execute("""
                SELECT c.relname FROM pg_class c
                WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'r'
                  AND NOT (has_table_privilege('service_role', c.oid, 'SELECT')
                       AND has_table_privilege('service_role', c.oid, 'INSERT')
                       AND has_table_privilege('service_role', c.oid, 'UPDATE')
                       AND has_table_privilege('service_role', c.oid, 'DELETE'))
            """)
            assert cur.fetchall() == []
