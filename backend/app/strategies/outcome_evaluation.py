from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math

from backend.app.analysis.bars import MarketBar
from backend.app.strategies.contract import READY, StrategyResult


MATURED = "matured"
IMMATURE = "immature"
NOT_APPLICABLE = "not_applicable"
UP = "up"
DOWN = "down"
FLAT = "flat"
OUTCOME_EVALUATOR_VERSION = "1.0.0"


@dataclass(frozen=True)
class OutcomeDefinition:
    evaluator_id: str = "forward_closed_bar_outcome"
    version: str = OUTCOME_EVALUATOR_VERSION
    lifecycle: str = "experimental"
    interpretation: str = "historical_outcome_measurement_not_trading_signal"


@dataclass(frozen=True)
class OutcomeObservation:
    bar_end_at: str
    status: str
    relation: str | None
    entry_close: float
    outcome_bar_end_at: str | None
    outcome_close: float | None
    return_percent: float | None
    direction: str | None


@dataclass(frozen=True)
class RelationOutcomeSummary:
    relation: str
    count: int
    up: int
    down: int
    flat: int
    mean_return_percent: float


@dataclass(frozen=True)
class OutcomeSummary:
    matured: int
    immature: int
    not_applicable: int
    up: int
    down: int
    flat: int
    mean_return_percent: float | None
    by_relation: tuple[RelationOutcomeSummary, ...]


@dataclass(frozen=True)
class StrategyOutcomeEvaluation:
    definition: OutcomeDefinition
    strategy_id: str
    strategy_version: str
    horizon_bars: int
    dataset_fingerprint: str
    bar_fingerprint: str
    strategy_fingerprint: str
    observations: tuple[OutcomeObservation, ...]
    summary: OutcomeSummary
    fingerprint: str
    interpretation: str = "historical_outcome_measurement_not_trading_signal"


def _fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def evaluate_strategy_outcomes(
    *, strategy: StrategyResult, bars: tuple[MarketBar, ...], horizon_bars: int
) -> StrategyOutcomeEvaluation:
    """Measure later closed-bar returns without changing the causal observation."""
    if horizon_bars < 1:
        raise ValueError("outcome horizon must be at least 1 bar")
    if len(bars) != len(strategy.observations):
        raise ValueError("bars and strategy observations must have the same length")

    observations: list[OutcomeObservation] = []
    relation_returns: dict[str, list[tuple[float, str]]] = {}
    immature = 0
    not_applicable = 0
    direction_counts = {UP: 0, DOWN: 0, FLAT: 0}

    for index, (bar, observation) in enumerate(
        zip(bars, strategy.observations, strict=True)
    ):
        if bar.end_at != observation.bar_end_at:
            raise ValueError("bars and strategy observations must be time-aligned")
        if observation.status != READY:
            not_applicable += 1
            observations.append(OutcomeObservation(
                observation.bar_end_at, NOT_APPLICABLE, observation.relation,
                observation.close, None, None, None, None,
            ))
            continue
        outcome_index = index + horizon_bars
        if outcome_index >= len(bars):
            immature += 1
            observations.append(OutcomeObservation(
                observation.bar_end_at, IMMATURE, observation.relation,
                observation.close, None, None, None, None,
            ))
            continue
        if not math.isfinite(observation.close) or observation.close <= 0:
            raise ValueError("strategy observation close must be positive and finite")
        outcome_bar = bars[outcome_index]
        if not math.isfinite(outcome_bar.close):
            raise ValueError("outcome bar close must be finite")
        return_percent = (outcome_bar.close / observation.close - 1.0) * 100.0
        direction = UP if return_percent > 0 else DOWN if return_percent < 0 else FLAT
        direction_counts[direction] += 1
        relation = observation.relation or "unclassified"
        relation_returns.setdefault(relation, []).append((return_percent, direction))
        observations.append(OutcomeObservation(
            observation.bar_end_at, MATURED, observation.relation,
            observation.close, outcome_bar.end_at, outcome_bar.close,
            return_percent, direction,
        ))

    relation_summaries = tuple(
        RelationOutcomeSummary(
            relation=relation,
            count=len(values),
            up=sum(direction == UP for _, direction in values),
            down=sum(direction == DOWN for _, direction in values),
            flat=sum(direction == FLAT for _, direction in values),
            mean_return_percent=math.fsum(value for value, _ in values) / len(values),
        )
        for relation, values in sorted(relation_returns.items())
    )
    matured = sum(direction_counts.values())
    all_returns = [
        item.return_percent for item in observations if item.return_percent is not None
    ]
    summary = OutcomeSummary(
        matured=matured,
        immature=immature,
        not_applicable=not_applicable,
        up=direction_counts[UP],
        down=direction_counts[DOWN],
        flat=direction_counts[FLAT],
        mean_return_percent=(math.fsum(all_returns) / matured if matured else None),
        by_relation=relation_summaries,
    )
    definition = OutcomeDefinition()
    payload: dict[str, object] = {
        "definition": asdict(definition),
        "strategy_id": strategy.definition.strategy_id,
        "strategy_version": strategy.definition.version,
        "horizon_bars": horizon_bars,
        "dataset_fingerprint": strategy.dataset_fingerprint,
        "bar_fingerprint": strategy.bar_fingerprint,
        "strategy_fingerprint": strategy.fingerprint,
        "observations": [asdict(item) for item in observations],
        "summary": asdict(summary),
    }
    return StrategyOutcomeEvaluation(
        definition=definition,
        strategy_id=strategy.definition.strategy_id,
        strategy_version=strategy.definition.version,
        horizon_bars=horizon_bars,
        dataset_fingerprint=strategy.dataset_fingerprint,
        bar_fingerprint=strategy.bar_fingerprint,
        strategy_fingerprint=strategy.fingerprint,
        observations=tuple(observations),
        summary=summary,
        fingerprint=_fingerprint(payload),
    )
