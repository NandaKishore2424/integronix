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
