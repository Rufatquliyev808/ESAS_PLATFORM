from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math

from backend.app.analysis.bars import MarketBar


INDICATOR_PACKAGE_VERSION = "1.0.0"
INSUFFICIENT_DATA = "insufficient_data"
READY = "ready"


@dataclass(frozen=True)
class IndicatorPoint:
    bar_end_at: str
    status: str
    value: float | None


@dataclass(frozen=True)
class IndicatorSeries:
    feature_id: str
    version: str
    period: int
    unit: str
    points: tuple[IndicatorPoint, ...]


@dataclass(frozen=True)
class IndicatorSetResult:
    ema: IndicatorSeries
    rsi: IndicatorSeries
    atr: IndicatorSeries
    bar_fingerprint: str
    fingerprint: str
    package_version: str = INDICATOR_PACKAGE_VERSION


def _validate_period(period: int) -> None:
    if isinstance(period, bool) or not isinstance(period, int) or period <= 0:
        raise ValueError("period must be a positive integer")


def _validated_bars(bars: tuple[MarketBar, ...]) -> tuple[MarketBar, ...]:
    previous_end: str | None = None
    symbol: str | None = None
    timeframe: str | None = None

    for bar in bars:
        if not all(
            math.isfinite(value)
            for value in (bar.open, bar.high, bar.low, bar.close)
        ):
            raise ValueError("bar prices must be finite")
        if bar.low > bar.high or not bar.low <= bar.open <= bar.high:
            raise ValueError("bar OHLC values are inconsistent")
        if not bar.low <= bar.close <= bar.high:
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


def _point(bar: MarketBar, value: float | None) -> IndicatorPoint:
    return IndicatorPoint(
        bar_end_at=bar.end_at,
        status=READY if value is not None else INSUFFICIENT_DATA,
        value=value,
    )


def calculate_ema(
    bars: tuple[MarketBar, ...], *, period: int
) -> IndicatorSeries:
    """Calculate a causal close-price EMA seeded by the first period SMA."""
    _validate_period(period)
    checked = _validated_bars(bars)
    points: list[IndicatorPoint] = []
    ema: float | None = None
    multiplier = 2.0 / (period + 1)

    for index, bar in enumerate(checked):
        if index + 1 < period:
            points.append(_point(bar, None))
            continue
        if ema is None:
            ema = sum(item.close for item in checked[:period]) / period
        else:
            ema = (bar.close - ema) * multiplier + ema
        points.append(_point(bar, ema))

    return IndicatorSeries(
        feature_id="ema.close",
        version="1.0.0",
        period=period,
        unit="price",
        points=tuple(points),
    )


def calculate_rsi(
    bars: tuple[MarketBar, ...], *, period: int
) -> IndicatorSeries:
    """Calculate causal Wilder RSI from closed-bar close changes."""
    _validate_period(period)
    checked = _validated_bars(bars)
    points: list[IndicatorPoint] = []
    average_gain: float | None = None
    average_loss: float | None = None

    for index, bar in enumerate(checked):
        if index < period:
            points.append(_point(bar, None))
            continue

        if average_gain is None or average_loss is None:
            changes = [
                checked[position].close - checked[position - 1].close
                for position in range(1, period + 1)
            ]
            average_gain = sum(max(change, 0.0) for change in changes) / period
            average_loss = sum(max(-change, 0.0) for change in changes) / period
        else:
            change = bar.close - checked[index - 1].close
            average_gain = (
                average_gain * (period - 1) + max(change, 0.0)
            ) / period
            average_loss = (
                average_loss * (period - 1) + max(-change, 0.0)
            ) / period

        if average_loss == 0:
            value = 100.0 if average_gain > 0 else 50.0
        else:
            relative_strength = average_gain / average_loss
            value = 100.0 - 100.0 / (1.0 + relative_strength)
        points.append(_point(bar, value))

    return IndicatorSeries(
        feature_id="rsi.wilder.close",
        version="1.0.0",
        period=period,
        unit="index_0_100",
        points=tuple(points),
    )


def calculate_atr(
    bars: tuple[MarketBar, ...], *, period: int
) -> IndicatorSeries:
    """Calculate causal Wilder ATR, using high-low for the first true range."""
    _validate_period(period)
    checked = _validated_bars(bars)
    points: list[IndicatorPoint] = []
    true_ranges: list[float] = []
    atr: float | None = None

    for index, bar in enumerate(checked):
        if index == 0:
            true_range = bar.high - bar.low
        else:
            previous_close = checked[index - 1].close
            true_range = max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        true_ranges.append(true_range)

        if index + 1 < period:
            points.append(_point(bar, None))
            continue
        if atr is None:
            atr = sum(true_ranges[:period]) / period
        else:
            atr = (atr * (period - 1) + true_range) / period
        points.append(_point(bar, atr))

    return IndicatorSeries(
        feature_id="atr.wilder",
        version="1.0.0",
        period=period,
        unit="price",
        points=tuple(points),
    )


def _fingerprint(
    *,
    ema: IndicatorSeries,
    rsi: IndicatorSeries,
    atr: IndicatorSeries,
    bar_fingerprint: str,
) -> str:
    payload = {
        "atr": asdict(atr),
        "bar_fingerprint": bar_fingerprint,
        "ema": asdict(ema),
        "package_version": INDICATOR_PACKAGE_VERSION,
        "rsi": asdict(rsi),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def build_indicator_set(
    bars: tuple[MarketBar, ...],
    *,
    bar_fingerprint: str,
    ema_period: int = 20,
    rsi_period: int = 14,
    atr_period: int = 14,
) -> IndicatorSetResult:
    """Build a deterministic read-only indicator package for closed bars."""
    checked = _validated_bars(bars)
    normalized_fingerprint = bar_fingerprint.strip()
    if not normalized_fingerprint:
        raise ValueError("bar_fingerprint must not be empty")

    ema = calculate_ema(checked, period=ema_period)
    rsi = calculate_rsi(checked, period=rsi_period)
    atr = calculate_atr(checked, period=atr_period)
    return IndicatorSetResult(
        ema=ema,
        rsi=rsi,
        atr=atr,
        bar_fingerprint=normalized_fingerprint,
        fingerprint=_fingerprint(
            ema=ema,
            rsi=rsi,
            atr=atr,
            bar_fingerprint=normalized_fingerprint,
        ),
    )
