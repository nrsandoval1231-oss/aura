"""Engineering-domain projection of Athena's directional outcome comparison.

Source: Athena f630acec86f1ff4aa03c0307fc77bd66a3f6bdc5,
src/athena_arena/evaluation.py::compare_vectors and contracts.py.
This is a narrow, attributed port of that algorithm, not the Arena/Gauntlet
GenerationRunner or a statistical policy-promotion implementation. A comparison
describes observed evidence; it never supplies execution authority.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from forge.learning import MeasurementVerdict, Metric, MetricDirection


def validate_metric(metric: Metric) -> None:
    if isinstance(metric.value, bool) or not math.isfinite(metric.value):
        raise ValueError("metrics require finite numeric observations")


@dataclass(frozen=True)
class EngineeringComparison:
    verdict: MeasurementVerdict
    delta: float | None
    reason: str
    execution_authority: bool = False

    def __post_init__(self) -> None:
        if self.execution_authority:
            raise ValueError("Athena comparison cannot grant execution authority")


def compare_outcomes(
    baseline: Metric,
    observed: Metric,
    *,
    baseline_context: str,
    observed_context: str,
    quality_passed: bool | None,
) -> EngineeringComparison:
    """Compare only the same registered task/protocol class and directional metric.

    Port Athena's delta * direction rule, using Forge's explicit metric direction
    instead of Athena's trading-era dimension-name map. A faster failed build is
    not an improvement. Context equality is a necessary condition, not statistical
    proof of causation or generalization across different slices.
    """
    validate_metric(baseline)
    validate_metric(observed)
    if (
        not baseline_context
        or baseline_context != observed_context
        or baseline.name != observed.name
        or baseline.direction is not observed.direction
    ):
        return EngineeringComparison(MeasurementVerdict.UNKNOWN, None, "Incomparable evidence")
    delta = observed.value - baseline.value
    if quality_passed is None:
        return EngineeringComparison(
            MeasurementVerdict.UNKNOWN, None, "Required quality evidence is incomplete"
        )
    if not quality_passed:
        return EngineeringComparison(
            MeasurementVerdict.HARMED, delta, "Required quality checks failed"
        )
    direction = -1 if observed.direction is MetricDirection.LOWER_IS_BETTER else 1
    verdict = MeasurementVerdict.UNCHANGED
    if delta * direction > 0:
        verdict = MeasurementVerdict.IMPROVED
    elif delta * direction < 0:
        verdict = MeasurementVerdict.HARMED
    return EngineeringComparison(verdict, delta, "Observed scoped comparison; not policy promotion")
