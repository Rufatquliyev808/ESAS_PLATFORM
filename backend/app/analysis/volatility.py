from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import statistics

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.return_series import ReturnSeriesResult


VOLATILITY_VERSION = "1.0.0"
QUANTILE_METHOD = "linear-interpolation-v1"
COMPLETED = "completed"
INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class DistributionSummary:
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
    p95: float | None


@dataclass(frozen=True)
class VolatilityResult:
    version: str
    symbol: str
    timeframe: str
    window_range_absolute: DistributionSummary
    window_range_relative: DistributionSummary
    window_log_return_abs: DistributionSummary
    robust_mad_status: str
    robust_mad: float | None
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


def _summarize(values: list[float], *, n_total: int, minimum_sample: int) -> DistributionSummary:
    n_valid = len(values)
    if n_valid < minimum_sample:
        return DistributionSummary(
            INSUFFICIENT_DATA, n_total, n_valid,
            None, None, None, None, None, None, None, None,
        )
    ordered = sorted(values)
    return DistributionSummary(
        COMPLETED, n_total, n_valid,
        len(ordered),
        statistics.fmean(ordered),
        statistics.median(ordered),
        statistics.stdev(ordered) if len(ordered) > 1 else 0.0,
        ordered[0],
        ordered[-1],
        _quantile(ordered, 0.05),
        _quantile(ordered, 0.95),
    )


def _fingerprint(
    *,
    bar_fingerprint: str,
    return_series_fingerprint: str,
    minimum_sample: int,
    window_range_absolute: DistributionSummary,
    window_range_relative: DistributionSummary,
    window_log_return_abs: DistributionSummary,
    robust_mad_status: str,
    robust_mad: float | None,
) -> str:
    payload = {
        "bar_fingerprint": bar_fingerprint,
        "return_series_fingerprint": return_series_fingerprint,
        "minimum_sample": minimum_sample,
        "robust_mad": robust_mad,
        "robust_mad_status": robust_mad_status,
        "version": VOLATILITY_VERSION,
        "window_log_return_abs": asdict(window_log_return_abs),
        "window_range_absolute": asdict(window_range_absolute),
        "window_range_relative": asdict(window_range_relative),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def compute_volatility(
    bars: tuple[MarketBar, ...],
    return_series: ReturnSeriesResult,
    *,
    bar_fingerprint: str,
    minimum_sample: int = 30,
) -> VolatilityResult:
    """Compute descriptive window-level volatility (SA-002) from closed bars
    and an already-computed return series over the same bars.

    Tick-to-tick return volatility is not computed here (it needs a raw tick
    pass, which only `bars.py` performs); this covers the window range and
    window-return-magnitude measures the contract also requires.
    """
    if isinstance(minimum_sample, bool) or not isinstance(minimum_sample, int) or minimum_sample < 1:
        raise ValueError("minimum_sample must be a positive integer")
    normalized_fingerprint = bar_fingerprint.strip()
    if not normalized_fingerprint:
        raise ValueError("bar_fingerprint must not be empty")
    for bar in bars:
        if bar.symbol != return_series.symbol or bar.timeframe != return_series.timeframe:
            raise ValueError("bars must match the return series symbol and timeframe")

    range_absolute = [bar.high - bar.low for bar in bars]
    range_relative = [(bar.high - bar.low) / bar.open for bar in bars]
    signed_returns = [window.log_return for window in return_series.windows]
    abs_returns = [abs(value) for value in signed_returns]

    window_range_absolute = _summarize(range_absolute, n_total=len(bars), minimum_sample=minimum_sample)
    window_range_relative = _summarize(range_relative, n_total=len(bars), minimum_sample=minimum_sample)
    window_log_return_abs = _summarize(
        abs_returns, n_total=len(return_series.windows), minimum_sample=minimum_sample
    )

    if len(signed_returns) < minimum_sample:
        robust_mad_status, robust_mad = INSUFFICIENT_DATA, None
    else:
        median_return = statistics.median(signed_returns)
        robust_mad = statistics.median(abs(value - median_return) for value in signed_returns)
        robust_mad_status = COMPLETED

    fingerprint = _fingerprint(
        bar_fingerprint=normalized_fingerprint,
        return_series_fingerprint=return_series.fingerprint,
        minimum_sample=minimum_sample,
        window_range_absolute=window_range_absolute,
        window_range_relative=window_range_relative,
        window_log_return_abs=window_log_return_abs,
        robust_mad_status=robust_mad_status,
        robust_mad=robust_mad,
    )

    return VolatilityResult(
        VOLATILITY_VERSION,
        return_series.symbol,
        return_series.timeframe,
        window_range_absolute,
        window_range_relative,
        window_log_return_abs,
        robust_mad_status,
        robust_mad,
        fingerprint,
    )
