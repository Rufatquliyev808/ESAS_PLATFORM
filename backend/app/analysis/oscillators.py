from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math

from backend.app.analysis.bars import MarketBar


OSCILLATOR_PACKAGE_VERSION = "1.0.0"
INSUFFICIENT_DATA = "insufficient_data"
READY = "ready"


@dataclass(frozen=True)
class OscillatorPoint:
    bar_end_at: str
    status: str
    value: float | None


@dataclass(frozen=True)
class OscillatorSeries:
    feature_id: str
    version: str
    period: int
    unit: str
    points: tuple[OscillatorPoint, ...]


@dataclass(frozen=True)
class OscillatorSetResult:
    stochastic_k: OscillatorSeries
    cci: OscillatorSeries
    adx: OscillatorSeries
    plus_di: OscillatorSeries
    minus_di: OscillatorSeries
    macd_line: OscillatorSeries
    macd_signal: OscillatorSeries
    williams_r: OscillatorSeries
    bar_fingerprint: str
    fingerprint: str
    package_version: str = OSCILLATOR_PACKAGE_VERSION


def _validate_period(period: int, name: str) -> None:
    if isinstance(period, bool) or not isinstance(period, int) or period <= 0:
        raise ValueError(f"{name} must be a positive integer")


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
        previous_end, symbol, timeframe = bar.end_at, bar.symbol, bar.timeframe
    return bars


def _point(bar: MarketBar, value: float | None) -> OscillatorPoint:
    return OscillatorPoint(bar_end_at=bar.end_at, status=READY if value is not None else INSUFFICIENT_DATA, value=value)


def _series(feature_id: str, version: str, period: int, unit: str, points: list[OscillatorPoint]) -> OscillatorSeries:
    return OscillatorSeries(feature_id=feature_id, version=version, period=period, unit=unit, points=tuple(points))


def calculate_stochastic_k(bars: tuple[MarketBar, ...], *, period: int = 14, smoothing: int = 3) -> OscillatorSeries:
    """Causal slow %K: raw %K over `period` closed bars, smoothed by an SMA of `smoothing` raw values."""
    _validate_period(period, "period")
    _validate_period(smoothing, "smoothing")
    checked = _validated_bars(bars)
    raw_k: list[float | None] = []
    for index, bar in enumerate(checked):
        if index + 1 < period:
            raw_k.append(None)
            continue
        window = checked[index + 1 - period: index + 1]
        highest = max(item.high for item in window)
        lowest = min(item.low for item in window)
        raw_k.append(50.0 if highest == lowest else (bar.close - lowest) / (highest - lowest) * 100.0)

    points: list[OscillatorPoint] = []
    for index, bar in enumerate(checked):
        window = [value for value in raw_k[index + 1 - smoothing: index + 1] if value is not None] if index + 1 >= smoothing else []
        value = sum(window) / len(window) if len(window) == smoothing else None
        points.append(_point(bar, value))
    return _series("stochastic.k", "1.0.0", period, "percent_0_100", points)


def calculate_cci(bars: tuple[MarketBar, ...], *, period: int = 20) -> OscillatorSeries:
    """Causal Commodity Channel Index. A zero mean-deviation window (flat range) yields CCI 0.0 (already the neutral value)."""
    _validate_period(period, "period")
    checked = _validated_bars(bars)
    typical = [(item.high + item.low + item.close) / 3.0 for item in checked]
    points: list[OscillatorPoint] = []
    for index, bar in enumerate(checked):
        if index + 1 < period:
            points.append(_point(bar, None))
            continue
        window = typical[index + 1 - period: index + 1]
        mean = sum(window) / period
        mean_deviation = sum(abs(value - mean) for value in window) / period
        value = 0.0 if mean_deviation == 0 else (typical[index] - mean) / (0.015 * mean_deviation)
        points.append(_point(bar, value))
    return _series("cci", "1.0.0", period, "index", points)


def calculate_williams_r(bars: tuple[MarketBar, ...], *, period: int = 14) -> OscillatorSeries:
    """Causal Williams %R. A zero-range window yields the midpoint -50.0."""
    _validate_period(period, "period")
    checked = _validated_bars(bars)
    points: list[OscillatorPoint] = []
    for index, bar in enumerate(checked):
        if index + 1 < period:
            points.append(_point(bar, None))
            continue
        window = checked[index + 1 - period: index + 1]
        highest = max(item.high for item in window)
        lowest = min(item.low for item in window)
        value = -50.0 if highest == lowest else (highest - bar.close) / (highest - lowest) * -100.0
        points.append(_point(bar, value))
    return _series("williams.r", "1.0.0", period, "percent_-100_0", points)


def calculate_macd(
    bars: tuple[MarketBar, ...], *, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9,
) -> tuple[OscillatorSeries, OscillatorSeries]:
    """Causal MACD line (EMA(fast) - EMA(slow) of closes) and its signal line (EMA(signal) of the MACD line)."""
    _validate_period(fast_period, "fast_period")
    _validate_period(slow_period, "slow_period")
    _validate_period(signal_period, "signal_period")
    if fast_period >= slow_period:
        raise ValueError("fast_period must be smaller than slow_period")
    checked = _validated_bars(bars)

    def ema_series(period: int) -> list[float | None]:
        values: list[float | None] = []
        ema: float | None = None
        multiplier = 2.0 / (period + 1)
        for index, bar in enumerate(checked):
            if index + 1 < period:
                values.append(None)
                continue
            if ema is None:
                ema = sum(item.close for item in checked[:period]) / period
            else:
                ema = (bar.close - ema) * multiplier + ema
            values.append(ema)
        return values

    fast_ema = ema_series(fast_period)
    slow_ema = ema_series(slow_period)
    macd_values = [
        None if fast is None or slow is None else fast - slow
        for fast, slow in zip(fast_ema, slow_ema)
    ]

    signal_values: list[float | None] = []
    signal_ema: float | None = None
    seed: list[float] = []
    signal_multiplier = 2.0 / (signal_period + 1)
    for value in macd_values:
        if value is None:
            signal_values.append(None)
            continue
        if signal_ema is None:
            seed.append(value)
            if len(seed) < signal_period:
                signal_values.append(None)
                continue
            signal_ema = sum(seed) / signal_period
        else:
            signal_ema = (value - signal_ema) * signal_multiplier + signal_ema
        signal_values.append(signal_ema)

    macd_points = [_point(bar, value) for bar, value in zip(checked, macd_values)]
    signal_points = [_point(bar, value) for bar, value in zip(checked, signal_values)]
    return (
        _series("macd.line", "1.0.0", slow_period, "price", macd_points),
        _series("macd.signal", "1.0.0", signal_period, "price", signal_points),
    )


def calculate_adx(
    bars: tuple[MarketBar, ...], *, period: int = 14,
) -> tuple[OscillatorSeries, OscillatorSeries, OscillatorSeries]:
    """Causal Wilder ADX with its +DI/-DI directional components."""
    _validate_period(period, "period")
    checked = _validated_bars(bars)

    true_ranges: list[float] = []
    plus_dms: list[float] = []
    minus_dms: list[float] = []
    for index, bar in enumerate(checked):
        if index == 0:
            true_ranges.append(bar.high - bar.low)
            plus_dms.append(0.0)
            minus_dms.append(0.0)
            continue
        previous = checked[index - 1]
        true_ranges.append(max(bar.high - bar.low, abs(bar.high - previous.close), abs(bar.low - previous.close)))
        up_move = bar.high - previous.high
        down_move = previous.low - bar.low
        plus_dms.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dms.append(down_move if down_move > up_move and down_move > 0 else 0.0)

    smoothed_tr: float | None = None
    smoothed_plus_dm: float | None = None
    smoothed_minus_dm: float | None = None
    plus_di_values: list[float | None] = []
    minus_di_values: list[float | None] = []
    dx_values: list[float | None] = []
    for index in range(len(checked)):
        if index + 1 < period:
            plus_di_values.append(None)
            minus_di_values.append(None)
            dx_values.append(None)
            continue
        if smoothed_tr is None:
            smoothed_tr = sum(true_ranges[:period])
            smoothed_plus_dm = sum(plus_dms[:period])
            smoothed_minus_dm = sum(minus_dms[:period])
        else:
            smoothed_tr = smoothed_tr - (smoothed_tr / period) + true_ranges[index]
            smoothed_plus_dm = smoothed_plus_dm - (smoothed_plus_dm / period) + plus_dms[index]
            smoothed_minus_dm = smoothed_minus_dm - (smoothed_minus_dm / period) + minus_dms[index]
        plus_di = 0.0 if smoothed_tr == 0 else 100.0 * smoothed_plus_dm / smoothed_tr
        minus_di = 0.0 if smoothed_tr == 0 else 100.0 * smoothed_minus_dm / smoothed_tr
        plus_di_values.append(plus_di)
        minus_di_values.append(minus_di)
        denominator = plus_di + minus_di
        dx_values.append(0.0 if denominator == 0 else 100.0 * abs(plus_di - minus_di) / denominator)

    adx_values: list[float | None] = []
    adx: float | None = None
    seed: list[float] = []
    for value in dx_values:
        if value is None:
            adx_values.append(None)
            continue
        if adx is None:
            seed.append(value)
            if len(seed) < period:
                adx_values.append(None)
                continue
            adx = sum(seed) / period
        else:
            adx = (adx * (period - 1) + value) / period
        adx_values.append(adx)

    adx_points = [_point(bar, value) for bar, value in zip(checked, adx_values)]
    plus_di_points = [_point(bar, value) for bar, value in zip(checked, plus_di_values)]
    minus_di_points = [_point(bar, value) for bar, value in zip(checked, minus_di_values)]
    return (
        _series("adx.wilder", "1.0.0", period, "index_0_100", adx_points),
        _series("di.plus", "1.0.0", period, "index_0_100", plus_di_points),
        _series("di.minus", "1.0.0", period, "index_0_100", minus_di_points),
    )


def _fingerprint(*, bar_fingerprint: str, series: dict[str, OscillatorSeries]) -> str:
    payload = {
        "bar_fingerprint": bar_fingerprint,
        "package_version": OSCILLATOR_PACKAGE_VERSION,
        **{name: asdict(item) for name, item in series.items()},
    }
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def build_oscillator_set(
    bars: tuple[MarketBar, ...],
    *,
    bar_fingerprint: str,
    stochastic_period: int = 14,
    stochastic_smoothing: int = 3,
    cci_period: int = 20,
    adx_period: int = 14,
    macd_fast_period: int = 12,
    macd_slow_period: int = 26,
    macd_signal_period: int = 9,
    williams_period: int = 14,
) -> OscillatorSetResult:
    """Build a deterministic, read-only oscillator package for closed bars."""
    checked = _validated_bars(bars)
    normalized_fingerprint = bar_fingerprint.strip()
    if not normalized_fingerprint:
        raise ValueError("bar_fingerprint must not be empty")

    stochastic_k = calculate_stochastic_k(checked, period=stochastic_period, smoothing=stochastic_smoothing)
    cci = calculate_cci(checked, period=cci_period)
    adx, plus_di, minus_di = calculate_adx(checked, period=adx_period)
    macd_line, macd_signal = calculate_macd(
        checked, fast_period=macd_fast_period, slow_period=macd_slow_period, signal_period=macd_signal_period,
    )
    williams_r = calculate_williams_r(checked, period=williams_period)

    return OscillatorSetResult(
        stochastic_k=stochastic_k, cci=cci, adx=adx, plus_di=plus_di, minus_di=minus_di,
        macd_line=macd_line, macd_signal=macd_signal, williams_r=williams_r,
        bar_fingerprint=normalized_fingerprint,
        fingerprint=_fingerprint(bar_fingerprint=normalized_fingerprint, series={
            "adx": adx, "cci": cci, "macd_line": macd_line, "macd_signal": macd_signal,
            "minus_di": minus_di, "plus_di": plus_di, "stochastic_k": stochastic_k, "williams_r": williams_r,
        }),
    )
