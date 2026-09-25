"""Governor budget enforcement.

The Finish Contract names budgets among what the Governor enforces, alongside state,
scope, authority and valid transitions. These tests are mostly about the ways a budget
can exist without bounding anything: charged after the fact, charged on a refusal,
declared but unlimited, or overspendable by asking twice.
"""

from __future__ import annotations

import pytest

from forge.governor import (
    Budget,
    BudgetDimension,
    BudgetLedger,
    GovernorError,
    SpendOutcome,
)

ATTEMPTS = BudgetDimension.ATTEMPTS
TOKENS = BudgetDimension.INPUT_TOKENS
CLOCK = BudgetDimension.WALL_CLOCK_SECONDS


def _ledger(**limits):
    return BudgetLedger("FORGE-T-001", Budget(**limits))


# ---------------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------------


def test_spending_within_budget_is_allowed():
    ledger = _ledger(attempts=3)
    assert ledger.spend(ATTEMPTS).outcome is SpendOutcome.ALLOWED
    assert ledger.spent(ATTEMPTS) == 1
    assert ledger.remaining(ATTEMPTS) == 2


def test_exhausting_a_budget_refuses_the_spend():
    ledger = _ledger(attempts=2)
    ledger.spend(ATTEMPTS)
    ledger.spend(ATTEMPTS)
    receipt = ledger.spend(ATTEMPTS)
    assert receipt.outcome is SpendOutcome.EXHAUSTED
    assert "must not proceed" in receipt.reason


def test_a_refused_spend_consumes_nothing():
    """A refusal that still charged would drift `remaining` away from reality."""
    ledger = _ledger(attempts=1)
    ledger.spend(ATTEMPTS)
    ledger.spend(ATTEMPTS)
    ledger.spend(ATTEMPTS)
    assert ledger.spent(ATTEMPTS) == 1
    assert ledger.remaining(ATTEMPTS) == 0


def test_a_spend_larger_than_the_whole_budget_is_refused_not_clamped():
    ledger = _ledger(input_tokens=100)
    assert ledger.spend(TOKENS, 500).outcome is SpendOutcome.EXHAUSTED
    assert ledger.spent(TOKENS) == 0


def test_a_spend_that_exactly_fits_is_allowed():
    ledger = _ledger(input_tokens=100)
    assert ledger.spend(TOKENS, 100).outcome is SpendOutcome.ALLOWED
    assert ledger.is_exhausted(TOKENS)


def test_asking_twice_does_not_overspend():
    """Exhaustion is not a warning that a caller can retry past."""
    ledger = _ledger(attempts=1)
    ledger.spend(ATTEMPTS)
    for _ in range(5):
        assert ledger.spend(ATTEMPTS).outcome is SpendOutcome.EXHAUSTED
    assert ledger.spent(ATTEMPTS) == 1


def test_dimensions_are_independent():
    ledger = _ledger(attempts=1, input_tokens=10)
    ledger.spend(ATTEMPTS)
    assert ledger.spend(TOKENS, 5).outcome is SpendOutcome.ALLOWED


def test_exhausted_dimensions_are_reported_together():
    ledger = _ledger(attempts=1, input_tokens=1)
    ledger.spend(ATTEMPTS)
    ledger.spend(TOKENS)
    assert ledger.exhausted_dimensions == frozenset({ATTEMPTS, TOKENS})


# ---------------------------------------------------------------------------
# Unlimited is explicit, not accidental
# ---------------------------------------------------------------------------


def test_an_unset_dimension_is_unlimited():
    ledger = _ledger(attempts=1)
    for _ in range(50):
        assert ledger.spend(TOKENS, 1000).outcome is SpendOutcome.ALLOWED


def test_remaining_on_an_unlimited_dimension_is_none_not_zero():
    """A number here would let a caller compare it and conclude something false."""
    assert _ledger().remaining(TOKENS) is None
    assert not _ledger().is_exhausted(TOKENS)


def test_declared_reports_which_dimensions_are_actually_bounded():
    assert Budget().declared == frozenset()
    assert Budget(attempts=3, wall_clock_seconds=60).declared == frozenset({ATTEMPTS, CLOCK})


def test_a_zero_limit_is_refused_because_none_means_unlimited():
    """Zero would silently mean "blocked", which is not what anyone writes it for."""
    with pytest.raises(GovernorError, match="permits no work at all"):
        Budget(attempts=0)


def test_a_negative_limit_is_refused():
    with pytest.raises(GovernorError, match="permits no work at all"):
        Budget(input_tokens=-1)


# ---------------------------------------------------------------------------
# A spend must be a cost
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("amount", [0, -1, -100])
def test_a_non_positive_spend_is_refused(amount):
    """A zero charge would let unlimited work through a bounded dimension."""
    with pytest.raises(GovernorError, match="not a cost"):
        _ledger(attempts=1).spend(ATTEMPTS, amount)


def test_a_budget_must_be_scoped_to_a_packet():
    with pytest.raises(GovernorError, match="scoped to a packet"):
        BudgetLedger("", Budget(attempts=1))


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


def test_every_spend_is_recorded_including_refusals():
    """A refusal is the moment a limit did something; dropping it hides the work."""
    ledger = _ledger(attempts=1)
    ledger.spend(ATTEMPTS)
    ledger.spend(ATTEMPTS)
    assert len(ledger.receipts) == 2
    assert [r.outcome for r in ledger.receipts] == [
        SpendOutcome.ALLOWED,
        SpendOutcome.EXHAUSTED,
    ]


def test_evidence_names_the_unbounded_dimensions():
    """ "Is this packet budgeted?" must not require reading five fields."""
    evidence = _ledger(attempts=2).evidence()
    assert evidence["declared_dimensions"] == [ATTEMPTS.value]
    assert TOKENS.value in evidence["unbounded_dimensions"]


def test_evidence_carries_the_refusals():
    ledger = _ledger(attempts=1)
    ledger.spend(ATTEMPTS)
    ledger.spend(ATTEMPTS)
    evidence = ledger.evidence()
    assert len(evidence["refusals"]) == 1
    assert evidence["exhausted"] == [ATTEMPTS.value]
    assert evidence["spend_count"] == 2


def test_receipts_are_content_addressed():
    ledger = _ledger(attempts=2)
    first = ledger.spend(ATTEMPTS)
    assert first.digest == first.digest
    assert first.digest != ledger.spend(ATTEMPTS).digest


def test_budget_digest_distinguishes_different_budgets():
    assert Budget(attempts=1).digest != Budget(attempts=2).digest
    assert Budget(attempts=1).digest == Budget(attempts=1).digest


# ---------------------------------------------------------------------------
# The two dimensions that bound a runaway regardless of provider
# ---------------------------------------------------------------------------


def test_wall_clock_and_attempts_can_both_be_bounded():
    """A loop that never calls a model can still spin; a free model can too.

    This is the pair that has to be set for a packet the loop actually runs. Tokens
    and currency are deliberately unset in V0 — no live call has been made, so there
    is no real figure to set them from, and inventing one would be a fabricated
    control rather than a cautious one.
    """
    budget = Budget(attempts=3, wall_clock_seconds=120)
    assert budget.declared >= frozenset({ATTEMPTS, CLOCK})
    ledger = BudgetLedger("FORGE-T-001", budget)
    assert ledger.spend(CLOCK, 119.5).outcome is SpendOutcome.ALLOWED
    assert ledger.spend(CLOCK, 1).outcome is SpendOutcome.EXHAUSTED


def test_fractional_wall_clock_spending_accumulates():
    ledger = _ledger(wall_clock_seconds=1.0)
    assert ledger.spend(CLOCK, 0.4).outcome is SpendOutcome.ALLOWED
    assert ledger.spend(CLOCK, 0.4).outcome is SpendOutcome.ALLOWED
    assert ledger.spend(CLOCK, 0.4).outcome is SpendOutcome.EXHAUSTED


def test_exhaustion_is_a_stop_not_a_grant():
    """Nothing on a receipt can be mistaken for permission to proceed."""
    ledger = _ledger(attempts=1)
    ledger.spend(ATTEMPTS)
    receipt = ledger.spend(ATTEMPTS)
    assert receipt.outcome is SpendOutcome.EXHAUSTED
    assert not hasattr(receipt, "authority")
    assert not hasattr(receipt, "grant")
    assert not hasattr(receipt, "override")


# ---------------------------------------------------------------------------
# Enforcement through the loop. A budget nothing consults is documentation.
# ---------------------------------------------------------------------------


def test_retry_limit_now_has_a_reader():
    """`BuildPacket.retry_limit` was declared by every packet and read by nothing.

    The packet contract calls it a retry budget. Before this it bounded nothing: a
    packet could declare two retries and take twenty.
    """
    import inspect

    from forge import execution_loop

    source = inspect.getsource(execution_loop.ExecutionLoop._spend_attempt)
    assert "retry_limit" in source
    assert "BudgetDimension.ATTEMPTS" in source
