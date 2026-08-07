from dataclasses import asdict, dataclass
from hashlib import sha256
from statistics import NormalDist
import json
import math

from backend.app.analysis.indicators import IndicatorSeries, IndicatorSetResult
from backend.app.analysis.liquidity_reaction import CONTINUED, REVERSED, ReactionEvent, ReactionStatistics
from backend.app.analysis.oscillators import OscillatorSeries, OscillatorSetResult


SEGMENT_VERSION = "1.0.0"
MIN_EFFECTIVE_SAMPLE = 30
COMPLETED = "completed"
INSUFFICIENT_DATA = "insufficient_data"
CONDITIONS = (
    "rsi_oversold", "rsi_overbought",
    "stochastic_oversold", "stochastic_overbought",
    "adx_trending",
)


@dataclass(frozen=True)
class IndicatorSegment:
    condition_id: str
    status: str
    n_total: int
    n_reversed: int
    n_continued: int
    reversed_percent: float | None
    confidence_interval_low_percent: float | None
    confidence_interval_high_percent: float | None
    baseline_reversed_percent: float | None
    exceeds_baseline: bool | None
    reason: str


@dataclass(frozen=True)
class LiquiditySegmentResult:
    version: str
    pool_side: str
    trial_count: int
    confidence_level_percent: float
    baseline: ReactionStatistics
    segments: tuple[IndicatorSegment, ...]
    fingerprint: str
    interpretation: str = "research_observation_not_trading_signal"


def _value_at(series: IndicatorSeries | OscillatorSeries, bar_index: int) -> float | None:
    if bar_index < 0 or bar_index >= len(series.points):
        return None
    return series.points[bar_index].value


def _condition_holds(
    condition_id: str, *, rsi: float | None, stochastic_k: float | None, adx: float | None,
) -> bool | None:
    if condition_id == "rsi_oversold":
        return None if rsi is None else rsi < 30.0
    if condition_id == "rsi_overbought":
        return None if rsi is None else rsi > 70.0
    if condition_id == "stochastic_oversold":
        return None if stochastic_k is None else stochastic_k < 20.0
    if condition_id == "stochastic_overbought":
        return None if stochastic_k is None else stochastic_k > 80.0
    if condition_id == "adx_trending":
        return None if adx is None else adx > 25.0
    raise ValueError(f"unknown condition_id: {condition_id}")


def _proportion_ci(reversed_count: int, total: int, z: float) -> tuple[float, float, float]:
    proportion = reversed_count / total
    margin = z * math.sqrt(proportion * (1 - proportion) / total)
    return proportion * 100.0, max(0.0, (proportion - margin) * 100.0), min(100.0, (proportion + margin) * 100.0)


def _baseline_statistics(pool_side: str, side_events: list[ReactionEvent]) -> ReactionStatistics:
    n_total = len(side_events)
    n_reversed = sum(1 for item in side_events if item.outcome == REVERSED)
    n_continued = sum(1 for item in side_events if item.outcome == CONTINUED)
    n_ambiguous = n_total - n_reversed - n_continued
    directional = n_reversed + n_continued
    if directional < MIN_EFFECTIVE_SAMPLE:
        return ReactionStatistics(pool_side, INSUFFICIENT_DATA, n_total, n_reversed, n_continued, n_ambiguous, None, None, None)
    pct, low, high = _proportion_ci(n_reversed, directional, 1.96)
    return ReactionStatistics(pool_side, COMPLETED, n_total, n_reversed, n_continued, n_ambiguous, pct, low, high)


def _fingerprint(*, pool_side: str, baseline: ReactionStatistics, segments: tuple[IndicatorSegment, ...]) -> str:
    payload = {
        "baseline": asdict(baseline),
        "pool_side": pool_side,
        "segments": [asdict(item) for item in segments],
        "version": SEGMENT_VERSION,
    }
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def find_indicator_segments(
    events: tuple[ReactionEvent, ...], pool_side: str,
    *, indicators: IndicatorSetResult, oscillators: OscillatorSetResult,
    confidence_level_percent: float = 95.0,
) -> LiquiditySegmentResult:
    """Search a fixed set of concurrent-indicator conditions (RSI/Stochastic
    oversold-overbought, ADX trending) at the touch bar, and report each
    condition's historical reversed-percentage among liquidity-level touches
    where it held. Because several conditions are tested against the same
    event set, the confidence interval for each uses a Bonferroni-corrected
    alpha (`(1 - confidence_level) / trial_count`) rather than the
    uncorrected 95% used for the plain baseline -- otherwise scanning enough
    conditions would eventually turn up a "significant" one by chance alone.
    A condition only counts as exceeding the baseline when its corrected
    confidence-interval floor is still above the baseline's point estimate.
    """
    if not 50.0 < confidence_level_percent < 100.0:
        raise ValueError("confidence_level_percent must be between 50 and 100")
    side_events = [item for item in events if item.pool_side == pool_side]
    directional_events = [item for item in side_events if item.outcome in (REVERSED, CONTINUED)]
    baseline = _baseline_statistics(pool_side, side_events)

    trial_count = len(CONDITIONS)
    alpha = (1.0 - confidence_level_percent / 100.0) / trial_count
    z = NormalDist().inv_cdf(1.0 - alpha / 2.0)

    segments: list[IndicatorSegment] = []
    for condition_id in CONDITIONS:
        matching = [
            event for event in directional_events
            if _condition_holds(
                condition_id,
                rsi=_value_at(indicators.rsi, event.bar_index),
                stochastic_k=_value_at(oscillators.stochastic_k, event.bar_index),
                adx=_value_at(oscillators.adx, event.bar_index),
            )
        ]
        n_total = len(matching)
        n_reversed = sum(1 for item in matching if item.outcome == REVERSED)
        n_continued = n_total - n_reversed
        if n_total < MIN_EFFECTIVE_SAMPLE:
            segments.append(IndicatorSegment(
                condition_id, INSUFFICIENT_DATA, n_total, n_reversed, n_continued,
                None, None, None, baseline.reversed_percent, None, "effective_sample_below_30",
            ))
            continue
        pct, low, high = _proportion_ci(n_reversed, n_total, z)
        exceeds = baseline.reversed_percent is not None and low > baseline.reversed_percent
        reason = "bonferroni_ci_low_exceeds_baseline" if exceeds else "ci_does_not_exceed_baseline"
        segments.append(IndicatorSegment(
            condition_id, COMPLETED, n_total, n_reversed, n_continued,
            pct, low, high, baseline.reversed_percent, exceeds, reason,
        ))

    return LiquiditySegmentResult(
        SEGMENT_VERSION, pool_side, trial_count, confidence_level_percent, baseline, tuple(segments),
        _fingerprint(pool_side=pool_side, baseline=baseline, segments=tuple(segments)),
    )
