from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
import math
import statistics

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.return_series import ReturnSeriesResult


SESSION_COMPARISON_VERSION = "1.0.0"
Z_95 = 1.96
COMPLETED = "completed"
INSUFFICIENT_DATA = "insufficient_data"
CALENDAR_UNAVAILABLE_LIMITATION = (
    "calendar_unavailable: no versioned symbol/broker session calendar "
    "exists yet (timezone, DST rule, weekend/holiday, overlapping-session "
    "priority). Buckets are grouped by raw UTC hour only and must not be "
    "read as named trading sessions (London, New York, Tokyo, ...)."
)


@dataclass(frozen=True)
class UtcHourBucketSummary:
    utc_hour: int
    status: str
    n_total_windows: int
    n_return_windows: int
    mean_return: float | None
    median_return: float | None
    return_std_dev: float | None
    return_confidence_interval_low: float | None
    return_confidence_interval_high: float | None
    mean_range_relative: float | None


@dataclass(frozen=True)
class SessionComparisonResult:
    version: str
    symbol: str
    timeframe: str
    calendar_unavailable: bool
    limitations: tuple[str, ...]
    buckets: tuple[UtcHourBucketSummary, ...]
    fingerprint: str
    interpretation: str = "research_observation_not_trading_signal"


def _hour(value: str) -> int:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).hour


def _fingerprint(
    *, bar_fingerprint: str, return_series_fingerprint: str, minimum_sample: int,
    buckets: tuple[UtcHourBucketSummary, ...],
) -> str:
    payload = {
        "version": SESSION_COMPARISON_VERSION, "bar_fingerprint": bar_fingerprint,
        "return_series_fingerprint": return_series_fingerprint,
        "minimum_sample": minimum_sample,
        "buckets": [asdict(item) for item in buckets],
    }
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def compute_session_comparison(
    bars: tuple[MarketBar, ...], return_series: ReturnSeriesResult, *,
    bar_fingerprint: str, minimum_sample: int = 30,
) -> SessionComparisonResult:
    """SA-006 session comparison, degraded mode: this platform has no
    versioned symbol/broker session calendar (timezone, DST rule,
    weekend/holiday, overlapping-session priority) -- the contract is
    explicit that without one, only raw UTC hour buckets may be shown, and
    they must never be presented as named trading sessions. That is exactly
    what this does: windows are grouped by `start_at`'s UTC hour (0-23), and
    each bucket reports the same descriptive metrics (return mean/median/
    std-dev with a 95% CI on the mean, and mean relative range as a
    volatility proxy) with its own sample size. A difference between
    buckets is a description of this dataset, not a trading edge -- the
    contract says so explicitly, and no code here should be read otherwise.

    Reuses `bars.py`'s bars and SA-001's already-computed `return_series`
    directly; no new raw-tick pass needed. `calendar_unavailable` and
    `limitations` are always populated to make the degraded mode
    impossible to miss in the API response.
    """
    if isinstance(minimum_sample, bool) or not isinstance(minimum_sample, int) or minimum_sample < 1:
        raise ValueError("minimum_sample must be a positive integer")
    normalized_fingerprint = bar_fingerprint.strip()
    if not normalized_fingerprint:
        raise ValueError("bar_fingerprint must not be empty")
    for bar in bars:
        if bar.symbol != return_series.symbol or bar.timeframe != return_series.timeframe:
            raise ValueError("bars must match the return series symbol and timeframe")

    return_by_start = {window.start_at: window.log_return for window in return_series.windows}
    total_by_hour: dict[int, list[MarketBar]] = {}
    for bar in bars:
        total_by_hour.setdefault(_hour(bar.start_at), []).append(bar)

    buckets: list[UtcHourBucketSummary] = []
    for hour in sorted(total_by_hour):
        hour_bars = total_by_hour[hour]
        n_total_windows = len(hour_bars)
        range_relative = [(bar.high - bar.low) / bar.open for bar in hour_bars]
        mean_range_relative = statistics.fmean(range_relative)
        returns = [
            return_by_start[bar.start_at] for bar in hour_bars if bar.start_at in return_by_start
        ]
        n_return_windows = len(returns)
        if n_return_windows < minimum_sample:
            buckets.append(
                UtcHourBucketSummary(
                    hour, INSUFFICIENT_DATA, n_total_windows, n_return_windows,
                    None, None, None, None, None, mean_range_relative,
                )
            )
            continue
        mean_return = statistics.fmean(returns)
        std_dev = statistics.stdev(returns) if len(returns) > 1 else 0.0
        margin = Z_95 * (std_dev / math.sqrt(n_return_windows))
        buckets.append(
            UtcHourBucketSummary(
                hour, COMPLETED, n_total_windows, n_return_windows,
                mean_return, statistics.median(returns), std_dev,
                mean_return - margin, mean_return + margin, mean_range_relative,
            )
        )

    fingerprint = _fingerprint(
        bar_fingerprint=normalized_fingerprint, return_series_fingerprint=return_series.fingerprint,
        minimum_sample=minimum_sample, buckets=tuple(buckets),
    )
    return SessionComparisonResult(
        SESSION_COMPARISON_VERSION, return_series.symbol, return_series.timeframe,
        True, (CALENDAR_UNAVAILABLE_LIMITATION,), tuple(buckets), fingerprint,
    )
