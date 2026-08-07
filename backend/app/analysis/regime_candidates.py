from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import statistics

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.return_series import ReturnSeriesResult


REGIME_VERSION = "1.0.0"
FEATURE_SCHEMA_VERSION = "1.0.0"
TIER_METHOD = "median_split_self_relative_v1"
COMPLETED = "completed"
INSUFFICIENT_DATA = "insufficient_data"
KNOWN_DATA_QUALITY_STATUSES = ("pass", "review", "fail")
LOW = "low"
HIGH = "high"
UP = "up"
DOWN = "down"
FLAT = "flat"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class RegimeWindowObservation:
    start_at: str
    end_at: str
    volatility_tier: str
    spread_tier: str
    tick_speed_tier: str
    return_direction: str
    regime: str


@dataclass(frozen=True)
class RegimeSummary:
    regime: str
    volatility_tier: str
    spread_tier: str
    tick_speed_tier: str
    return_direction: str
    observation_count: int
    confidence: float
    first_observed_at: str
    last_observed_at: str


@dataclass(frozen=True)
class RegimeCandidatesResult:
    version: str
    symbol: str
    timeframe: str
    status: str
    n_total_windows: int
    n_classified_windows: int
    data_quality_status: str
    feature_schema_version: str
    tier_method: str
    regimes: tuple[RegimeSummary, ...]
    observations: tuple[RegimeWindowObservation, ...]
    fingerprint: str
    interpretation: str = "research_observation_not_trading_signal"


def _median(values: list[float]) -> float:
    return statistics.median(values)


def _tier(value: float, median: float) -> str:
    return HIGH if value >= median else LOW


def _return_direction(log_return: float | None) -> str:
    if log_return is None:
        return UNKNOWN
    if log_return > 0:
        return UP
    if log_return < 0:
        return DOWN
    return FLAT


def _fingerprint(
    *, bar_fingerprint: str, return_series_fingerprint: str, data_quality_status: str,
    minimum_sample: int, regimes: tuple[RegimeSummary, ...],
    observations: tuple[RegimeWindowObservation, ...],
) -> str:
    payload = {
        "version": REGIME_VERSION, "bar_fingerprint": bar_fingerprint,
        "return_series_fingerprint": return_series_fingerprint,
        "data_quality_status": data_quality_status, "minimum_sample": minimum_sample,
        "regimes": [asdict(item) for item in regimes],
        "observations": [asdict(item) for item in observations],
    }
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def compute_regime_candidates(
    bars: tuple[MarketBar, ...], return_series: ReturnSeriesResult, *,
    bar_fingerprint: str, data_quality_status: str, minimum_sample: int = 30,
) -> RegimeCandidatesResult:
    """SA-007 market regime candidates: an initial, purely descriptive
    clustering of windows by four already-computed features (volatility
    level, spread level, tick speed, return direction), reusing SA-002's
    range, SA-003's spread, SA-001's return sign and each bar's own
    `tick_count` -- no new raw-tick pass needed.

    Volatility/spread/tick-speed are each bucketed `low`/`high` by a median
    split WITHIN this dataset (`tier_method`); there is no universal or
    annualized threshold, so a window's tier is only meaningful relative to
    the rest of the same analysis run, never across different runs. Each
    distinct (volatility_tier, spread_tier, tick_speed_tier,
    return_direction) combination observed is assigned an arbitrary,
    lexicographically-ordered `regime_N` label -- the contract is explicit
    that regime names must not carry economic meaning ("trend", "range",
    "risky") unless separately validated, and none of that validation has
    happened here. Regime labels are therefore NOT stable across different
    datasets or re-runs with a different window set; only the feature tuple
    attached to each regime is comparable.

    `data_quality_status` is the whole replay session's Phase 2 quality
    status (`pass`/`review`/`fail`), attached uniformly to every window in
    this result -- this platform does not track quality per window, only
    per session, so it is deliberately not varied across windows. A window
    with fewer than two ticks has no computable return (`return_series.py`
    excludes it), so its return direction is `unknown`, not `flat`.
    """
    if isinstance(minimum_sample, bool) or not isinstance(minimum_sample, int) or minimum_sample < 1:
        raise ValueError("minimum_sample must be a positive integer")
    normalized_fingerprint = bar_fingerprint.strip()
    if not normalized_fingerprint:
        raise ValueError("bar_fingerprint must not be empty")
    if data_quality_status not in KNOWN_DATA_QUALITY_STATUSES:
        raise ValueError(f"data_quality_status must be one of: {', '.join(KNOWN_DATA_QUALITY_STATUSES)}")
    for bar in bars:
        if bar.symbol != return_series.symbol or bar.timeframe != return_series.timeframe:
            raise ValueError("bars must match the return series symbol and timeframe")

    symbol = return_series.symbol
    timeframe = return_series.timeframe
    n_total_windows = len(bars)

    if n_total_windows < minimum_sample:
        fingerprint = _fingerprint(
            bar_fingerprint=normalized_fingerprint, return_series_fingerprint=return_series.fingerprint,
            data_quality_status=data_quality_status, minimum_sample=minimum_sample,
            regimes=(), observations=(),
        )
        return RegimeCandidatesResult(
            REGIME_VERSION, symbol, timeframe, INSUFFICIENT_DATA, n_total_windows, 0,
            data_quality_status, FEATURE_SCHEMA_VERSION, TIER_METHOD, (), (), fingerprint,
        )

    return_by_start = {window.start_at: window.log_return for window in return_series.windows}
    volatility_values = [(bar.high - bar.low) / bar.open for bar in bars]
    spread_values = [(bar.spread_mean / bar.close) * 10_000 for bar in bars]
    tick_values = [float(bar.tick_count) for bar in bars]
    volatility_median = _median(volatility_values)
    spread_median = _median(spread_values)
    tick_median = _median(tick_values)

    observations: list[RegimeWindowObservation] = []
    feature_keys: list[tuple[str, str, str, str]] = []
    for bar, volatility_value, spread_value, tick_value in zip(bars, volatility_values, spread_values, tick_values):
        volatility_tier = _tier(volatility_value, volatility_median)
        spread_tier = _tier(spread_value, spread_median)
        tick_speed_tier = _tier(tick_value, tick_median)
        return_direction = _return_direction(return_by_start.get(bar.start_at))
        feature_key = (volatility_tier, spread_tier, tick_speed_tier, return_direction)
        feature_keys.append(feature_key)
        observations.append(
            RegimeWindowObservation(
                bar.start_at, bar.end_at, volatility_tier, spread_tier, tick_speed_tier,
                return_direction, "",
            )
        )

    distinct_keys = sorted(set(feature_keys))
    regime_by_key = {key: f"regime_{index + 1}" for index, key in enumerate(distinct_keys)}
    observations = [
        RegimeWindowObservation(
            item.start_at, item.end_at, item.volatility_tier, item.spread_tier,
            item.tick_speed_tier, item.return_direction, regime_by_key[key],
        )
        for item, key in zip(observations, feature_keys)
    ]

    regimes: list[RegimeSummary] = []
    for key in distinct_keys:
        regime = regime_by_key[key]
        members = [item for item, member_key in zip(observations, feature_keys) if member_key == key]
        regimes.append(
            RegimeSummary(
                regime, key[0], key[1], key[2], key[3],
                len(members), len(members) / n_total_windows,
                min(item.start_at for item in members),
                max(item.start_at for item in members),
            )
        )

    fingerprint = _fingerprint(
        bar_fingerprint=normalized_fingerprint, return_series_fingerprint=return_series.fingerprint,
        data_quality_status=data_quality_status, minimum_sample=minimum_sample,
        regimes=tuple(regimes), observations=tuple(observations),
    )
    return RegimeCandidatesResult(
        REGIME_VERSION, symbol, timeframe, COMPLETED, n_total_windows, len(observations),
        data_quality_status, FEATURE_SCHEMA_VERSION, TIER_METHOD,
        tuple(regimes), tuple(observations), fingerprint,
    )
