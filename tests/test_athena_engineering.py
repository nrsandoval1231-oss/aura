from dataclasses import replace

import pytest

from forge.athena_engineering import EngineeringComparison, compare_outcomes
from forge.learning import MeasurementVerdict, Metric, MetricDirection


def compare(before=3, after=1, **kwargs):
    baseline = Metric("attempts_to_green", before, MetricDirection.LOWER_IS_BETTER)
    values = dict(baseline_context="imports:v1", observed_context="imports:v1", quality_passed=True)
    values.update(kwargs)
    return compare_outcomes(baseline, replace(baseline, value=after), **values)


def test_directional_comparison_and_quality_guardrail():
    assert compare().verdict is MeasurementVerdict.IMPROVED
    assert compare(1, 3).verdict is MeasurementVerdict.HARMED
    assert compare(1, 1).verdict is MeasurementVerdict.UNCHANGED
    assert compare(3, 1, quality_passed=False).verdict is MeasurementVerdict.HARMED
    assert compare(observed_context="different:v2").verdict is MeasurementVerdict.UNKNOWN
    before = Metric("checks_passed", 2, MetricDirection.HIGHER_IS_BETTER)
    assert (
        compare_outcomes(
            before,
            replace(before, value=4),
            baseline_context="x",
            observed_context="x",
            quality_passed=True,
        ).verdict
        is MeasurementVerdict.IMPROVED
    )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True])
def test_invalid_metrics_cannot_generate_improvement(value):
    with pytest.raises(ValueError):
        compare(after=value)


def test_comparisons_never_authorize_execution():
    assert not compare().execution_authority
    with pytest.raises(ValueError):
        EngineeringComparison(MeasurementVerdict.IMPROVED, -1, "test", True)
