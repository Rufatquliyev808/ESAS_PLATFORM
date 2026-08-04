from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math

from backend.app.analysis.bars import MarketBar
from backend.app.strategies.contract import StrategyResult
from backend.app.strategies.outcome_evaluation import (
    DOWN,
    FLAT,
    IMMATURE,
    MATURED,
    NOT_APPLICABLE,
    UP,
    OutcomeObservation,
    RelationOutcomeSummary,
    StrategyOutcomeEvaluation,
)


WALK_FORWARD_VERSION = "1.0.0"
READY = "ready"
INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class WalkForwardDefinition:
    evaluator_id: str = "chronological_holdout_comparison"
    version: str = WALK_FORWARD_VERSION
    lifecycle: str = "experimental"
    interpretation: str = "historical_holdout_research_not_trading_signal"


@dataclass(frozen=True)
class WalkForwardWindowSummary:
    window: str
    start_bar_end_at: str | None
    end_bar_end_at: str | None
    total_observations: int
    matured: int
    immature: int
    not_applicable: int
    boundary_excluded: int
    up: int
    down: int
    flat: int
    mean_return_percent: float | None
    by_relation: tuple[RelationOutcomeSummary, ...]


@dataclass(frozen=True)
class WalkForwardManifest:
    strategy_id: str
    strategy_version: str
    parameters: tuple[tuple[str, int | float | str], ...]
    parameter_source: str
    split_policy: str
    development_ratio: float
    split_index: int
    total_bars: int
    outcome_horizon_bars: int
    dataset_fingerprint: str
    bar_fingerprint: str
    strategy_fingerprint: str
    outcome_fingerprint: str


@dataclass(frozen=True)
class WalkForwardEvaluation:
    definition: WalkForwardDefinition
    status: str
    manifest: WalkForwardManifest
    development: WalkForwardWindowSummary
    validation: WalkForwardWindowSummary
    fingerprint: str
    interpretation: str = "historical_holdout_research_not_trading_signal"


def _fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _summarize(
    *, name: str, bars: tuple[MarketBar, ...], observations: tuple[OutcomeObservation, ...],
    start: int, end: int, split_index: int, horizon_bars: int,
) -> WalkForwardWindowSummary:
    counts = {UP: 0, DOWN: 0, FLAT: 0}
    immature = not_applicable = boundary_excluded = 0
    relation_returns: dict[str, list[tuple[float, str]]] = {}

    for index in range(start, end):
        observation = observations[index]
        if name == "development" and observation.status == MATURED and index + horizon_bars >= split_index:
            boundary_excluded += 1
            continue
        if observation.status == IMMATURE:
            immature += 1
            continue
        if observation.status == NOT_APPLICABLE:
            not_applicable += 1
            continue
        if observation.status != MATURED or observation.return_percent is None or observation.direction is None:
            raise ValueError("outcome observation has an unsupported state")
        counts[observation.direction] += 1
        relation = observation.relation or "unclassified"
        relation_returns.setdefault(relation, []).append((observation.return_percent, observation.direction))

    by_relation = tuple(
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
    matured = sum(counts.values())
    returns = [value for values in relation_returns.values() for value, _ in values]
    return WalkForwardWindowSummary(
        window=name,
        start_bar_end_at=bars[start].end_at if start < end else None,
        end_bar_end_at=bars[end - 1].end_at if start < end else None,
        total_observations=end - start,
        matured=matured,
        immature=immature,
        not_applicable=not_applicable,
        boundary_excluded=boundary_excluded,
        up=counts[UP], down=counts[DOWN], flat=counts[FLAT],
        mean_return_percent=math.fsum(returns) / matured if matured else None,
        by_relation=by_relation,
    )


def evaluate_walk_forward(
    *, strategy: StrategyResult, outcome: StrategyOutcomeEvaluation,
    bars: tuple[MarketBar, ...], development_ratio: float,
) -> WalkForwardEvaluation:
    """Compare a chronological development window with an untouched validation window."""
    if not 0.5 <= development_ratio <= 0.9:
        raise ValueError("development ratio must be between 0.5 and 0.9")
    if len(bars) != len(strategy.observations) or len(bars) != len(outcome.observations):
        raise ValueError("bars, strategy and outcome observations must have the same length")
    if outcome.strategy_fingerprint != strategy.fingerprint:
        raise ValueError("outcome evaluation belongs to another strategy result")
    for bar, strategy_observation, outcome_observation in zip(
        bars, strategy.observations, outcome.observations, strict=True
    ):
        if bar.end_at != strategy_observation.bar_end_at or bar.end_at != outcome_observation.bar_end_at:
            raise ValueError("walk-forward inputs must be time-aligned")

    total = len(bars)
    split_index = max(1, min(total - 1, math.floor(total * development_ratio))) if total >= 2 else total
    development = _summarize(
        name="development", bars=bars, observations=outcome.observations,
        start=0, end=split_index, split_index=split_index,
        horizon_bars=outcome.horizon_bars,
    )
    validation = _summarize(
        name="validation", bars=bars, observations=outcome.observations,
        start=split_index, end=total, split_index=split_index,
        horizon_bars=outcome.horizon_bars,
    )
    manifest = WalkForwardManifest(
        strategy_id=strategy.definition.strategy_id,
        strategy_version=strategy.definition.version,
        parameters=strategy.parameters,
        parameter_source="development_configuration",
        split_policy="chronological_no_shuffle_validation_untouched",
        development_ratio=development_ratio,
        split_index=split_index,
        total_bars=total,
        outcome_horizon_bars=outcome.horizon_bars,
        dataset_fingerprint=strategy.dataset_fingerprint,
        bar_fingerprint=strategy.bar_fingerprint,
        strategy_fingerprint=strategy.fingerprint,
        outcome_fingerprint=outcome.fingerprint,
    )
    definition = WalkForwardDefinition()
    status = READY if total >= 2 else INSUFFICIENT_DATA
    payload: dict[str, object] = {
        "definition": asdict(definition), "status": status,
        "manifest": asdict(manifest), "development": asdict(development),
        "validation": asdict(validation),
    }
    return WalkForwardEvaluation(
        definition=definition, status=status, manifest=manifest,
        development=development, validation=validation,
        fingerprint=_fingerprint(payload),
    )
