from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.indicators import calculate_ema


MOVING_AVERAGE_PACKAGE_VERSION = "1.0.0"
INSUFFICIENT_DATA = "insufficient_data"
READY = "ready"
SMA = "sma"
EMA = "ema"
# TradingView's technical-analysis widget shows one EMA and one SMA row per
# period across a handful of standard periods; this mirrors that shape
# (4 periods x 2 types = 8 moving averages) without touching indicators.py's
# stable, widely-reused calculate_ema().
MOVING_AVERAGE_PERIODS = (10, 20, 30, 50)


@dataclass(frozen=True)
class MovingAveragePoint:
    bar_end_at: str
    status: str
    value: float | None


@dataclass(frozen=True)
class MovingAverageSeries:
    feature_id: str
    ma_type: str
    version: str
    period: int
    unit: str
    points: tuple[MovingAveragePoint, ...]


@dataclass(frozen=True)
class MovingAverageSetResult:
    series: tuple[MovingAverageSeries, ...]
    bar_fingerprint: str
    fingerprint: str
    package_version: str = MOVING_AVERAGE_PACKAGE_VERSION


def _validate_period(period: int) -> None:
    if isinstance(period, bool) or not isinstance(period, int) or period <= 0:
        raise ValueError("period must be a positive integer")


def _validated_bars(bars: tuple[MarketBar, ...]) -> tuple[MarketBar, ...]:
    previous_end: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    for bar in bars:
        if not all(math.isfinite(value) for value in (bar.open, bar.high, bar.low, bar.close)):
            raise ValueError("bar prices must be finite")
        if bar.low > bar.high or not bar.low <= bar.close <= bar.high:
            raise ValueError("bar OHLC values are inconsistent")
        if previous_end is not None and bar.start_at < previous_end:
            raise ValueError("bars must be ordered and non-overlapping")
        if symbol is not None and bar.symbol != symbol:
            raise ValueError("bars must use one symbol")
        if timeframe is not None and bar.timeframe != timeframe:
            raise ValueError("bars must use one timeframe")
        previous_end = bar.end_at
        symbol = bar.symbol
        timeframe = bar.timeframe
    return bars


def _point(bar: MarketBar, value: float | None) -> MovingAveragePoint:
    return MovingAveragePoint(bar_end_at=bar.end_at, status=READY if value is not None else INSUFFICIENT_DATA, value=value)


def calculate_sma(bars: tuple[MarketBar, ...], *, period: int) -> MovingAverageSeries:
    """Causal simple moving average of closes: each point is the mean of that
    bar's own close and the `period - 1` closes before it -- no forward-fill,
    no lookahead."""
    _validate_period(period)
    checked = _validated_bars(bars)
    points: list[MovingAveragePoint] = []
    window_sum = 0.0

    for index, bar in enumerate(checked):
        window_sum += bar.close
        if index >= period:
            window_sum -= checked[index - period].close
        if index + 1 < period:
            points.append(_point(bar, None))
            continue
        points.append(_point(bar, window_sum / period))

    return MovingAverageSeries(
        feature_id=f"sma.close.{period}", ma_type=SMA, version="1.0.0",
        period=period, unit="price", points=tuple(points),
    )


def _from_ema(ema_series, period: int) -> MovingAverageSeries:
    points = tuple(MovingAveragePoint(item.bar_end_at, item.status, item.value) for item in ema_series.points)
    return MovingAverageSeries(
        feature_id=f"ema.close.{period}", ma_type=EMA, version=ema_series.version,
        period=period, unit=ema_series.unit, points=points,
    )


def _fingerprint(*, bar_fingerprint: str, series: tuple[MovingAverageSeries, ...]) -> str:
    payload = {
        "bar_fingerprint": bar_fingerprint,
        "package_version": MOVING_AVERAGE_PACKAGE_VERSION,
        "series": [asdict(item) for item in series],
    }
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def build_moving_average_set(
    bars: tuple[MarketBar, ...], *, bar_fingerprint: str, periods: tuple[int, ...] = MOVING_AVERAGE_PERIODS,
) -> MovingAverageSetResult:
    """Build the causal SMA+EMA set (one of each per period) used by the live
    indicator consensus panel's moving-average table. `calculate_ema()` is
    reused directly from `indicators.py` (already causal, already tested);
    only SMA is new here.
    """
    checked = _validated_bars(bars)
    normalized_fingerprint = bar_fingerprint.strip()
    if not normalized_fingerprint:
        raise ValueError("bar_fingerprint must not be empty")
    if not periods:
        raise ValueError("periods must not be empty")

    series: list[MovingAverageSeries] = []
    for period in periods:
        series.append(calculate_sma(checked, period=period))
        series.append(_from_ema(calculate_ema(checked, period=period), period))

    result_series = tuple(series)
    return MovingAverageSetResult(
        series=result_series, bar_fingerprint=normalized_fingerprint,
        fingerprint=_fingerprint(bar_fingerprint=normalized_fingerprint, series=result_series),
    )
