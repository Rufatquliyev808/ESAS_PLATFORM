from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import statistics

from backend.app.analysis.bars import MarketBar


SPREAD_VERSION = "1.0.0"
QUANTILE_METHOD = "linear-interpolation-v1"
COMPLETED = "completed"
INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class SpreadDistributionSummary:
    status: str
    n_total: int
    n_valid: int
    count: int | None
    mean: float | None
    median: float | None
    std_dev: float | None
    minimum: float | None
    maximum: float | None
    p05: float | None
    p25: float | None
    p75: float | None
    p95: float | None
    p99: float | None


@dataclass(frozen=True)
class SpreadResult:
    version: str
    symbol: str
    timeframe: str
    window_spread_absolute: SpreadDistributionSummary
    window_spread_relative_bps: SpreadDistributionSummary
    fingerprint: str
    quantile_method: str = QUANTILE_METHOD
    interpretation: str = "research_observation_not_trading_signal"


def _quantile(ordered: list[float], fraction: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _summarize(values: list[float], *, n_total: int, minimum_sample: int) -> SpreadDistributionSummary:
    n_valid = len(values)
    if n_valid < minimum_sample:
        return SpreadDistributionSummary(
            INSUFFICIENT_DATA, n_total, n_valid,
            None, None, None, None, None, None, None, None, None, None, None,
        )
    ordered = sorted(values)
    return SpreadDistributionSummary(
        COMPLETED, n_total, n_valid,
        len(ordered),
        statistics.fmean(ordered),
        statistics.median(ordered),
        statistics.stdev(ordered) if len(ordered) > 1 else 0.0,
        ordered[0],
        ordered[-1],
        _quantile(ordered, 0.05),
        _quantile(ordered, 0.25),
        _quantile(ordered, 0.75),
        _quantile(ordered, 0.95),
        _quantile(ordered, 0.99),
    )


def _fingerprint(
    *, bar_fingerprint: str, minimum_sample: int,
    window_spread_absolute: SpreadDistributionSummary,
    window_spread_relative_bps: SpreadDistributionSummary,
) -> str:
    payload = {
        "bar_fingerprint": bar_fingerprint,
        "minimum_sample": minimum_sample,
        "version": SPREAD_VERSION,
        "window_spread_absolute": asdict(window_spread_absolute),
        "window_spread_relative_bps": asdict(window_spread_relative_bps),
    }
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def compute_spread_statistics(
    bars: tuple[MarketBar, ...], *, bar_fingerprint: str, minimum_sample: int = 30,
) -> SpreadResult:
    """SA-003 spread behaviour: descriptive statistics (count, mean, median,
    std-dev, min, max, p05/p25/p75/p95/p99) of each window's own mean spread
    (already computed causally, tick-by-tick, in `bars.py` -- no new raw-tick
    pass needed here), both in absolute price terms and relative to that
    window's close price (in bps). `spread_points` (the contract's point/digit
    -denominated variant) is deliberately omitted: this platform has no
    confirmed symbol point/digit metadata source, and the contract says not
    to fabricate it when that metadata is unavailable.
    """
    if isinstance(minimum_sample, bool) or not isinstance(minimum_sample, int) or minimum_sample < 1:
        raise ValueError("minimum_sample must be a positive integer")
    normalized_fingerprint = bar_fingerprint.strip()
    if not normalized_fingerprint:
        raise ValueError("bar_fingerprint must not be empty")
    symbol = bars[0].symbol if bars else ""
    timeframe = bars[0].timeframe if bars else ""

    absolute_values = [bar.spread_mean for bar in bars]
    relative_values = [(bar.spread_mean / bar.close) * 10_000 for bar in bars]

    window_spread_absolute = _summarize(absolute_values, n_total=len(bars), minimum_sample=minimum_sample)
    window_spread_relative_bps = _summarize(relative_values, n_total=len(bars), minimum_sample=minimum_sample)

    return SpreadResult(
        SPREAD_VERSION, symbol, timeframe,
        window_spread_absolute, window_spread_relative_bps,
        _fingerprint(
            bar_fingerprint=normalized_fingerprint, minimum_sample=minimum_sample,
            window_spread_absolute=window_spread_absolute,
            window_spread_relative_bps=window_spread_relative_bps,
        ),
    )
