from dataclasses import asdict, dataclass
from hashlib import sha256
from math import log
import json
import statistics

from backend.app.analysis.bars import MarketBar


RETURN_SERIES_VERSION = "1.0.0"
QUANTILE_METHOD = "linear-interpolation-v1"
COMPLETED = "completed"
INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class WindowReturn:
    start_at: str
    end_at: str
    tick_count: int
    open_mid: float
    close_mid: float
    log_return: float


@dataclass(frozen=True)
class ReturnSeriesResult:
    version: str
    symbol: str
    timeframe: str
    status: str
    n_total: int
    n_valid: int
    n_excluded: int
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
    windows: tuple[WindowReturn, ...]
    fingerprint: str
    quantile_method: str = QUANTILE_METHOD
    interpretation: str = "research_observation_not_trading_signal"


def _validate_bars(bars: tuple[MarketBar, ...], *, symbol: str, timeframe: str) -> None:
    previous_end: str | None = None
    for bar in bars:
        if bar.symbol != symbol or bar.timeframe != timeframe:
            raise ValueError("bars must match the requested symbol and timeframe")
        if previous_end is not None and bar.start_at < previous_end:
            raise ValueError("bars must be ordered and non-overlapping")
        previous_end = bar.end_at


def _quantile(ordered: list[float], fraction: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _fingerprint(
    *,
    bar_fingerprint: str,
    minimum_window_returns: int,
    windows: tuple[WindowReturn, ...],
) -> str:
    payload = {
        "bar_fingerprint": bar_fingerprint,
        "minimum_window_returns": minimum_window_returns,
        "version": RETURN_SERIES_VERSION,
        "windows": [asdict(item) for item in windows],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def compute_return_series(
    bars: tuple[MarketBar, ...],
    *,
    symbol: str,
    timeframe: str,
    bar_fingerprint: str,
    minimum_window_returns: int = 30,
) -> ReturnSeriesResult:
    """Compute per-window log-returns (SA-001) from closed, causal mid-price bars.

    A window's return uses only its own first (open) and last (close) valid
    mid-price, so a single-tick window has no first/last pair and yields no
    return (excluded, not treated as a zero-return observation). An empty
    bar set (no ticks in range) is a valid degenerate input, not an error.
    """
    if isinstance(minimum_window_returns, bool) or not isinstance(minimum_window_returns, int) or minimum_window_returns < 1:
        raise ValueError("minimum_window_returns must be a positive integer")
    normalized_fingerprint = bar_fingerprint.strip()
    if not normalized_fingerprint:
        raise ValueError("bar_fingerprint must not be empty")
    normalized_symbol = symbol.strip()
    if not normalized_symbol:
        raise ValueError("symbol must not be empty")
    _validate_bars(bars, symbol=normalized_symbol, timeframe=timeframe)

    windows: list[WindowReturn] = []
    excluded = 0
    for bar in bars:
        if bar.tick_count < 2 or bar.open <= 0 or bar.close <= 0:
            excluded += 1
            continue
        windows.append(
            WindowReturn(
                start_at=bar.start_at,
                end_at=bar.end_at,
                tick_count=bar.tick_count,
                open_mid=bar.open,
                close_mid=bar.close,
                log_return=log(bar.close / bar.open),
            )
        )

    n_total, n_valid, n_excluded = len(bars), len(windows), excluded
    fingerprint = _fingerprint(
        bar_fingerprint=normalized_fingerprint,
        minimum_window_returns=minimum_window_returns,
        windows=tuple(windows),
    )

    if n_valid < minimum_window_returns:
        return ReturnSeriesResult(
            RETURN_SERIES_VERSION, normalized_symbol, timeframe, INSUFFICIENT_DATA,
            n_total, n_valid, n_excluded,
            None, None, None, None, None, None, None, None, None, None,
            tuple(windows), fingerprint,
        )

    returns = sorted(item.log_return for item in windows)
    return ReturnSeriesResult(
        RETURN_SERIES_VERSION, normalized_symbol, timeframe, COMPLETED,
        n_total, n_valid, n_excluded,
        len(returns),
        statistics.fmean(returns),
        statistics.median(returns),
        statistics.stdev(returns) if len(returns) > 1 else 0.0,
        returns[0],
        returns[-1],
        _quantile(returns, 0.05),
        _quantile(returns, 0.25),
        _quantile(returns, 0.75),
        _quantile(returns, 0.95),
        tuple(windows),
        fingerprint,
    )
