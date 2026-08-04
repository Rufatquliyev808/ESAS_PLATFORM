from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math

from backend.app.analysis.bars import MarketBar
from backend.app.strategies.contract import StrategyResult
from backend.app.strategies.outcome_evaluation import StrategyOutcomeEvaluation
from backend.app.strategies.walk_forward_evaluation import (
    INSUFFICIENT_DATA,
    READY,
    WalkForwardWindowSummary,
    _summarize,
)


MULTI_WINDOW_VERSION = "1.0.0"


@dataclass(frozen=True)
class MultiWindowDefinition:
    evaluator_id: str = "expanding_chronological_validation_windows"
    version: str = MULTI_WINDOW_VERSION
    lifecycle: str = "experimental"
    interpretation: str = "historical_stability_research_not_trading_signal"


@dataclass(frozen=True)
class ValidationWindowManifest:
    window_number: int
    development_start_index: int
    development_end_index_exclusive: int
    validation_start_index: int
    validation_end_index_exclusive: int
    development_bar_fingerprint: str
    validation_bar_fingerprint: str
    upstream_strategy_fingerprint: str
    upstream_outcome_fingerprint: str


@dataclass(frozen=True)
class ValidationWindow:
    window_number: int
    development: WalkForwardWindowSummary
    validation: WalkForwardWindowSummary
    manifest: ValidationWindowManifest
    fingerprint: str


@dataclass(frozen=True)
class StabilitySummary:
    requested_windows: int
    completed_windows: int
    windows_with_matured_observations: int
    positive_windows: int
    negative_windows: int
    flat_windows: int
    total_validation_observations: int
    matured_validation_observations: int
    immature_validation_observations: int
    not_applicable_validation_observations: int
    weighted_mean_return_percent: float | None
    minimum_window_mean_return_percent: float | None
    maximum_window_mean_return_percent: float | None
    return_range_percentage_points: float | None


@dataclass(frozen=True)
class MultiWindowManifest:
    strategy_id: str
    strategy_version: str
    parameters: tuple[tuple[str, int | float | str], ...]
    parameter_source: str
    split_policy: str
    development_ratio: float
    requested_windows: int
    initial_development_bars: int
    total_bars: int
    outcome_horizon_bars: int
    dataset_fingerprint: str
    bar_fingerprint: str
    strategy_fingerprint: str
    outcome_fingerprint: str


@dataclass(frozen=True)
class MultiWindowEvaluation:
    definition: MultiWindowDefinition
    status: str
    summary: StabilitySummary
    windows: tuple[ValidationWindow, ...]
    manifest: MultiWindowManifest
    fingerprint: str
    interpretation: str = "historical_stability_research_not_trading_signal"


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _bar_slice_fingerprint(bars: tuple[MarketBar, ...], start: int, end: int) -> str:
    return _fingerprint([
        {
            "end_at": bar.end_at,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "tick_count": bar.tick_count,
        }
        for bar in bars[start:end]
    ])


def _validate_inputs(
    *, strategy: StrategyResult, outcome: StrategyOutcomeEvaluation,
    bars: tuple[MarketBar, ...], development_ratio: float, window_count: int,
) -> None:
    if not 0.5 <= development_ratio <= 0.9:
        raise ValueError("development ratio must be between 0.5 and 0.9")
    if not 2 <= window_count <= 8:
        raise ValueError("window count must be between 2 and 8")
    if len(bars) != len(strategy.observations) or len(bars) != len(outcome.observations):
        raise ValueError("bars, strategy and outcome observations must have the same length")
    if outcome.strategy_fingerprint != strategy.fingerprint:
        raise ValueError("outcome evaluation belongs to another strategy result")
    for bar, strategy_observation, outcome_observation in zip(
        bars, strategy.observations, outcome.observations, strict=True
    ):
        if bar.end_at != strategy_observation.bar_end_at or bar.end_at != outcome_observation.bar_end_at:
            raise ValueError("multi-window inputs must be time-aligned")


def evaluate_multi_window_walk_forward(
    *, strategy: StrategyResult, outcome: StrategyOutcomeEvaluation,
    bars: tuple[MarketBar, ...], development_ratio: float, window_count: int,
) -> MultiWindowEvaluation:
    """Measure descriptive stability on expanding, non-overlapping future windows."""
    _validate_inputs(
        strategy=strategy, outcome=outcome, bars=bars,
        development_ratio=development_ratio, window_count=window_count,
    )
    total = len(bars)
    initial_development = (
        max(1, min(total - 1, math.floor(total * development_ratio)))
        if total >= 2 else total
    )
    validation_bars = total - initial_development
    actual_windows = min(window_count, validation_bars)
    base_size, extra = divmod(validation_bars, actual_windows) if actual_windows else (0, 0)
    windows: list[ValidationWindow] = []
    validation_start = initial_development

    for offset in range(actual_windows):
        validation_end = validation_start + base_size + (1 if offset < extra else 0)
        number = offset + 1
        development = _summarize(
            name="development", bars=bars, observations=outcome.observations,
            start=0, end=validation_start, split_index=validation_start,
            horizon_bars=outcome.horizon_bars,
        )
        validation = _summarize(
            name="validation", bars=bars, observations=outcome.observations,
            start=validation_start, end=validation_end, split_index=validation_start,
            horizon_bars=outcome.horizon_bars,
        )
        fold_manifest = ValidationWindowManifest(
            window_number=number,
            development_start_index=0,
            development_end_index_exclusive=validation_start,
            validation_start_index=validation_start,
            validation_end_index_exclusive=validation_end,
            development_bar_fingerprint=_bar_slice_fingerprint(bars, 0, validation_start),
            validation_bar_fingerprint=_bar_slice_fingerprint(bars, validation_start, validation_end),
            upstream_strategy_fingerprint=strategy.fingerprint,
            upstream_outcome_fingerprint=outcome.fingerprint,
        )
        fold_payload = {
            "window_number": number,
            "development": asdict(development),
            "validation": asdict(validation),
            "manifest": asdict(fold_manifest),
        }
        windows.append(ValidationWindow(
            window_number=number,
            development=development,
            validation=validation,
            manifest=fold_manifest,
            fingerprint=_fingerprint(fold_payload),
        ))
        validation_start = validation_end

    means = [
        window.validation.mean_return_percent for window in windows
        if window.validation.mean_return_percent is not None
    ]
    matured = sum(window.validation.matured for window in windows)
    weighted_sum = math.fsum(
        (window.validation.mean_return_percent or 0.0) * window.validation.matured
        for window in windows
    )
    minimum = min(means) if means else None
    maximum = max(means) if means else None
    summary = StabilitySummary(
        requested_windows=window_count,
        completed_windows=len(windows),
        windows_with_matured_observations=len(means),
        positive_windows=sum(value > 0 for value in means),
        negative_windows=sum(value < 0 for value in means),
        flat_windows=sum(value == 0 for value in means),
        total_validation_observations=sum(window.validation.total_observations for window in windows),
        matured_validation_observations=matured,
        immature_validation_observations=sum(window.validation.immature for window in windows),
        not_applicable_validation_observations=sum(window.validation.not_applicable for window in windows),
        weighted_mean_return_percent=weighted_sum / matured if matured else None,
        minimum_window_mean_return_percent=minimum,
        maximum_window_mean_return_percent=maximum,
        return_range_percentage_points=maximum - minimum if minimum is not None and maximum is not None else None,
    )
    manifest = MultiWindowManifest(
        strategy_id=strategy.definition.strategy_id,
        strategy_version=strategy.definition.version,
        parameters=strategy.parameters,
        parameter_source="fixed_development_configuration",
        split_policy="expanding_development_non_overlapping_chronological_validation_no_shuffle",
        development_ratio=development_ratio,
        requested_windows=window_count,
        initial_development_bars=initial_development,
        total_bars=total,
        outcome_horizon_bars=outcome.horizon_bars,
        dataset_fingerprint=strategy.dataset_fingerprint,
        bar_fingerprint=strategy.bar_fingerprint,
        strategy_fingerprint=strategy.fingerprint,
        outcome_fingerprint=outcome.fingerprint,
    )
    definition = MultiWindowDefinition()
    status = READY if len(windows) >= 2 else INSUFFICIENT_DATA
    payload = {
        "definition": asdict(definition), "status": status,
        "summary": asdict(summary), "windows": [asdict(window) for window in windows],
        "manifest": asdict(manifest),
    }
    return MultiWindowEvaluation(
        definition=definition, status=status, summary=summary,
        windows=tuple(windows), manifest=manifest,
        fingerprint=_fingerprint(payload),
    )
