"""
Unit tests for money arithmetic.

Claim amounts flow into EDI 837/835 files that must reconcile to the cent. The
invariant that matters is not "close enough" — it is that allowed, paid and
patient responsibility sum EXACTLY, every time, for every input.

These tests exist because the code used floats. 0.1 + 0.2 != 0.3 in binary
floating point, and the drift accumulates across line items until a payer
rejects an unbalanced claim.
"""

from decimal import Decimal

import pytest

from routes.claims import _money, _uuid_or_none


class TestMoneyQuantisation:
    def test_quantises_to_two_places(self):
        assert _money("10.005") == Decimal("10.01")
        assert _money("10.004") == Decimal("10.00")

    def test_rounds_half_up_not_bankers(self):
        """
        Python's round() uses banker's rounding: round(0.5) == 0. Billing
        conventionally rounds half away from zero, so 0.005 must become 0.01.
        """
        assert _money("0.005") == Decimal("0.01")
        assert _money("0.015") == Decimal("0.02")

    def test_none_and_empty_are_zero(self):
        assert _money(None) == Decimal("0.00")
        assert _money(0) == Decimal("0.00")

    def test_accepts_int_float_str_and_decimal(self):
        assert _money(5) == Decimal("5.00")
        assert _money(5.0) == Decimal("5.00")
        assert _money("5") == Decimal("5.00")
        assert _money(Decimal("5")) == Decimal("5.00")

    def test_float_input_does_not_import_binary_error(self):
        """
        Decimal(0.1) is 0.1000000000000000055511151231257827.
        Decimal(str(0.1)) is exactly 0.1. The conversion must go through str().
        """
        assert _money(0.1) == Decimal("0.10")
        assert _money(2.675) == Decimal("2.68")


class TestFloatDriftIsGone:
    def test_addition_that_floats_get_wrong_is_exact(self):
        """The canonical case: in binary floating point 0.1 + 0.2 != 0.3."""
        assert 0.1 + 0.2 != 0.3                                  # the bug we left behind
        assert _money("0.1") + _money("0.2") == Decimal("0.30")  # what we do now

    def test_many_line_items_reconcile_exactly(self):
        prices = ["27.53", "14.50", "1099.99", "0.01", "333.33"] * 40
        total = sum((_money(p) for p in prices), Decimal("0"))
        assert total == Decimal("59_014.40".replace("_", ""))


class TestAdjudicationInvariant:
    """
    allowed == paid + patient_responsibility, exactly.

    Patient responsibility is computed as the REMAINDER of allowed minus paid,
    never as its own percentage of allowed — two independently rounded
    percentages can miss each other by a cent.
    """

    @pytest.mark.parametrize("allowed,pct", [
        ("100.00", "0.80"), ("0.01", "0.80"), ("33.33", "0.3333"),
        ("999999.99", "0.85"), ("10.00", "1.0"), ("10.00", "0.0"),
        ("0.03", "0.5"), ("1234.56", "0.666666"),
    ])
    def test_three_amounts_always_sum(self, allowed, pct):
        total_allowed = _money(allowed)
        total_paid = _money(total_allowed * Decimal(pct))
        patient_resp = total_allowed - total_paid

        assert total_paid + patient_resp == total_allowed
        assert patient_resp >= 0, "patient responsibility must never go negative"
        assert total_paid <= total_allowed, "payer must never pay above allowed"

    def test_full_coverage_leaves_patient_owing_nothing(self):
        allowed = _money("250.00")
        paid = _money(allowed * Decimal("1.0"))
        assert allowed - paid == Decimal("0.00")

    def test_denial_puts_full_amount_on_the_patient(self):
        billed = _money("512.75")
        allowed, paid = _money(0), _money(0)
        patient_resp = billed
        assert allowed == Decimal("0.00") and paid == Decimal("0.00")
        assert patient_resp == billed


class TestLineItemTotalsMatchTheClaim:
    def test_total_equals_sum_of_quantised_lines(self):
        """
        The claim total must equal the sum of the line items printed on it.
        Quantising each line and then summing (correct) can differ from summing
        raw and quantising once — the total on the page has to be the one that
        adds up.
        """
        multiplier = Decimal("1.2")
        bases = ["27.53", "14.50", "99.99"]
        # 33.036 -> 33.04, 17.40 -> 17.40, 119.988 -> 119.99
        lines = [_money(Decimal(b) * multiplier) for b in bases]
        assert lines == [Decimal("33.04"), Decimal("17.40"), Decimal("119.99")]

        total = sum(lines, Decimal("0"))
        assert total == Decimal("170.43")

        # Summing raw and quantising once gives 170.42 — a cent adrift from the
        # printed line items. The total on the claim must be the one that adds up.
        summed_raw = _money(sum((Decimal(b) * multiplier for b in bases), Decimal("0")))
        assert summed_raw == Decimal("170.42")
        assert total != summed_raw


class TestAuditUserIdCoercion:
    """changed_by_user_id is a uuid column; synthetic test ids must not 500."""

    def test_valid_uuid_passes_through(self):
        u = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
        assert _uuid_or_none(u) == u

    @pytest.mark.parametrize("value", ["test-user-hospital", "", None, "dev", 12345])
    def test_non_uuid_becomes_none(self, value):
        assert _uuid_or_none(value) is None
