"""
Unit tests for the pipeline's safety mechanisms and money arithmetic.

Two things are covered here, both introduced this week and both invisible to
the integration suite when it is skipped in CI:

  * @safe_node's fail-closed short-circuit — the guard that stops a failed run
    from being dressed up as a confident result.
  * financial_calculator's Decimal arithmetic — the numbers that end up on
    the claim.
"""

import asyncio
from decimal import Decimal

import pytest

from agents.financial_calculator import (
    DEFAULT_MULTIPLIER,
    _cents,
    financial_calculator_node,
)
from agents.node_runner import safe_node


def run(coro):
    return asyncio.run(coro)


# ── Fail-closed graph behaviour ──────────────────────────────────────────────

class TestSafeNodeShortCircuit:
    """
    Before this guard, a crashing node wrote error_at and the graph carried on:
    four more nodes ran against half-built state, each crashed on None, and the
    endpoint returned HTTP 200 with a confident-looking empty result. For a
    billing engine, converting a failure into a plausible success is the worst
    available failure mode.
    """

    def test_records_the_failing_node_rather_than_raising(self):
        @safe_node("exploder")
        async def node(state):
            raise ValueError("boom")

        state = run(node({"session_id": "s1"}))
        assert state["error_at"] == "exploder"
        assert "boom" in state["error_detail"]

    def test_downstream_nodes_are_skipped_after_a_failure(self):
        ran = []

        @safe_node("first")
        async def first(state):
            raise RuntimeError("upstream failed")

        @safe_node("second")
        async def second(state):
            ran.append("second")
            state["result"] = "computed on broken state"
            return state

        state = run(first({"session_id": "s1"}))
        state = run(second(state))

        assert ran == [], "a node must not run after an upstream failure"
        assert "result" not in state
        assert state["error_at"] == "first", "the original failure point is preserved"

    def test_healthy_nodes_run_normally(self):
        @safe_node("worker")
        async def node(state):
            state["done"] = True
            return state

        state = run(node({"session_id": "s1"}))
        assert state["done"] is True
        assert state.get("error_at") is None

    def test_first_failure_wins(self):
        """error_at must point at the root cause, not the last node to notice."""
        @safe_node("first")
        async def first(state):
            raise RuntimeError("root cause")

        @safe_node("second")
        async def second(state):
            raise RuntimeError("secondary")

        state = run(second(run(first({"session_id": "s1"}))))
        assert state["error_at"] == "first"
        assert "root cause" in state["error_detail"]


# ── Money in the pipeline ────────────────────────────────────────────────────

class TestFinancialCalculatorMoney:
    CPT = [
        {"code": "71045", "description": "Chest X-Ray", "type": "CPT", "base_price": 27.53},
        {"code": "J0131", "description": "IV acetaminophen", "type": "HCPCS", "base_price": 14.50},
    ]

    def test_total_equals_the_sum_of_the_line_items(self, fake_db):
        """The claim total must be exactly what the printed lines add up to."""
        fake_db.on("select_one", {"cpt_pricing_multiplier": 1.2})
        state = run(financial_calculator_node({
            "session_id": "s1", "org_id": "org-1", "cpt_codes": list(self.CPT),
        }))

        summary = state["financial_summary"]
        line_total = sum(_cents(li["gross_charge"]) for li in summary["line_items"])
        assert _cents(summary["total_estimated_revenue"]) == line_total

    def test_multiplier_is_applied_per_line(self, fake_db):
        fake_db.on("select_one", {"cpt_pricing_multiplier": 1.2})
        state = run(financial_calculator_node({
            "session_id": "s1", "org_id": "org-1", "cpt_codes": list(self.CPT),
        }))

        lines = {li["code"]: li for li in state["financial_summary"]["line_items"]}
        assert _cents(lines["71045"]["gross_charge"]) == Decimal("33.04")  # 27.53 * 1.2
        assert _cents(lines["J0131"]["gross_charge"]) == Decimal("17.40")  # 14.50 * 1.2
        assert _cents(state["financial_summary"]["total_estimated_revenue"]) == Decimal("50.44")

    def test_missing_org_uses_the_default_never_another_tenants_rate(self, fake_db):
        """
        Regression: with no org_id this read `org_settings LIMIT 1` and priced
        the encounter with a DIFFERENT hospital's multiplier — wrong money and
        a tenant-boundary crossing, with nothing in the output to show it.
        """
        state = run(financial_calculator_node({
            "session_id": "s1", "org_id": None, "cpt_codes": list(self.CPT),
        }))

        summary = state["financial_summary"]
        assert summary["pricing_multiplier"] == float(DEFAULT_MULTIPLIER)
        assert not [c for c in fake_db.calls if c[0] == "select_one"], \
            "no org means no settings lookup at all"

    def test_unavailable_settings_fall_back_to_default(self, fake_db):
        fake_db.on("select_one", RuntimeError("database unreachable"))
        state = run(financial_calculator_node({
            "session_id": "s1", "org_id": "org-1", "cpt_codes": list(self.CPT),
        }))
        assert state["financial_summary"]["pricing_multiplier"] == float(DEFAULT_MULTIPLIER)

    def test_falls_back_to_icd_reimbursement_without_cpt_codes(self, fake_db):
        state = run(financial_calculator_node({
            "session_id": "s1", "org_id": "org-1", "cpt_codes": [],
            "icd_codes": [{"code": "J18.9", "base_reimbursement": 1200.50}],
        }))
        assert state["financial_summary"]["total_estimated_revenue"] == 1200.50
        assert state["financial_summary"]["line_items"] == []

    def test_no_codes_at_all_produces_zero_not_a_crash(self, fake_db):
        state = run(financial_calculator_node({
            "session_id": "s1", "org_id": "org-1", "cpt_codes": [], "icd_codes": [],
        }))
        assert state["financial_summary"]["total_estimated_revenue"] == 0.0

    def test_amounts_are_json_serialisable(self, fake_db):
        """Decimal is not JSON-serialisable; the node must hand back floats."""
        import json

        fake_db.on("select_one", {"cpt_pricing_multiplier": 1.2})
        state = run(financial_calculator_node({
            "session_id": "s1", "org_id": "org-1", "cpt_codes": list(self.CPT),
        }))
        json.dumps(state["financial_summary"])  # must not raise

    def test_skipped_when_an_upstream_node_failed(self, fake_db):
        """financial_calc carries @safe_node, so the short-circuit applies."""
        state = run(financial_calculator_node({
            "session_id": "s1", "org_id": "org-1", "cpt_codes": list(self.CPT),
            "error_at": "icd_decision",
        }))
        assert "financial_summary" not in state


class TestCentsHelper:
    @pytest.mark.parametrize("value,expected", [
        ("10.005", "10.01"), (None, "0.00"), (0, "0.00"),
        (27.53, "27.53"), (Decimal("1.234"), "1.23"),
    ])
    def test_quantisation(self, value, expected):
        assert _cents(value) == Decimal(expected)
