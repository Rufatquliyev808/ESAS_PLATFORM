from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.indicators import IndicatorSetResult
from backend.app.analysis.oscillators import OscillatorSetResult


CONSENSUS_VERSION = "2.0.0"
BULLISH_LEANING = "bullish_leaning"
BEARISH_LEANING = "bearish_leaning"
NEUTRAL = "neutral"
INSUFFICIENT_DATA = "insufficient_data"
RSI_OVERSOLD_THRESHOLD = 30.0
RSI_OVERBOUGHT_THRESHOLD = 70.0
STOCHASTIC_OVERSOLD_THRESHOLD = 20.0
STOCHASTIC_OVERBOUGHT_THRESHOLD = 80.0
CCI_OVERSOLD_THRESHOLD = -100.0
CCI_OVERBOUGHT_THRESHOLD = 100.0
WILLIAMS_R_OVERSOLD_THRESHOLD = -80.0
WILLIAMS_R_OVERBOUGHT_THRESHOLD = -20.0
ADX_TRENDING_THRESHOLD = 25.0


@dataclass(frozen=True)
class IndicatorLean:
    indicator_id: str
    status: str
    value: float | None
    reference: float | None


@dataclass(frozen=True)
class ConsensusSummary:
    bullish_leaning_count: int
    bearish_leaning_count: int
    neutral_count: int
    insufficient_data_count: int
    overall_lean: str


@dataclass(frozen=True)
class IndicatorConsensusResult:
    version: str
    oscillators: tuple[IndicatorLean, ...]
    moving_averages: tuple[IndicatorLean, ...]
    oscillator_summary: ConsensusSummary
    moving_average_summary: ConsensusSummary
    overall_summary: ConsensusSummary
    fingerprint: str
    interpretation: str = "research_observation_not_trading_signal"


def _classify_rsi(value: float | None) -> IndicatorLean:
    """RSI < 30 is classically read as oversold (bullish-leaning), > 70 overbought (bearish-leaning)."""
    return _classify_below_oversold_above_overbought(
        "rsi", value, oversold=RSI_OVERSOLD_THRESHOLD, overbought=RSI_OVERBOUGHT_THRESHOLD,
    )


def _classify_price_vs_average(indicator_id: str, average: float | None, close: float) -> IndicatorLean:
    if average is None:
        return IndicatorLean(indicator_id, INSUFFICIENT_DATA, None, close)
    if close > average:
        return IndicatorLean(indicator_id, BULLISH_LEANING, average, close)
    if close < average:
        return IndicatorLean(indicator_id, BEARISH_LEANING, average, close)
    return IndicatorLean(indicator_id, NEUTRAL, average, close)


def _classify_below_oversold_above_overbought(
    indicator_id: str, value: float | None, *, oversold: float, overbought: float,
) -> IndicatorLean:
    """Shared shape for oscillators where a low reading is oversold (bullish-leaning)
    and a high reading is overbought (bearish-leaning): RSI, Stochastic %K, CCI, Williams %R."""
    if value is None:
        return IndicatorLean(indicator_id, INSUFFICIENT_DATA, None, None)
    if value < oversold:
        return IndicatorLean(indicator_id, BULLISH_LEANING, value, oversold)
    if value > overbought:
        return IndicatorLean(indicator_id, BEARISH_LEANING, value, overbought)
    return IndicatorLean(indicator_id, NEUTRAL, value, None)


def _classify_macd(macd_line: float | None, macd_signal: float | None) -> IndicatorLean:
    if macd_line is None or macd_signal is None:
        return IndicatorLean("macd", INSUFFICIENT_DATA, None, None)
    if macd_line > macd_signal:
        return IndicatorLean("macd", BULLISH_LEANING, macd_line, macd_signal)
    if macd_line < macd_signal:
        return IndicatorLean("macd", BEARISH_LEANING, macd_line, macd_signal)
    return IndicatorLean("macd", NEUTRAL, macd_line, macd_signal)


def _classify_adx(adx: float | None, plus_di: float | None, minus_di: float | None) -> IndicatorLean:
    """ADX measures trend strength, not direction, so it is only directional when
    combined with +DI/-DI and only above the trending threshold; a weak trend
    (ADX below threshold) is reported neutral regardless of +DI/-DI position."""
    if adx is None or plus_di is None or minus_di is None:
        return IndicatorLean("adx", INSUFFICIENT_DATA, None, None)
    if adx > ADX_TRENDING_THRESHOLD and plus_di > minus_di:
        return IndicatorLean("adx", BULLISH_LEANING, adx, ADX_TRENDING_THRESHOLD)
    if adx > ADX_TRENDING_THRESHOLD and minus_di > plus_di:
        return IndicatorLean("adx", BEARISH_LEANING, adx, ADX_TRENDING_THRESHOLD)
    return IndicatorLean("adx", NEUTRAL, adx, ADX_TRENDING_THRESHOLD)


def _summarize(leans: tuple[IndicatorLean, ...]) -> ConsensusSummary:
    bullish = sum(1 for item in leans if item.status == BULLISH_LEANING)
    bearish = sum(1 for item in leans if item.status == BEARISH_LEANING)
    neutral = sum(1 for item in leans if item.status == NEUTRAL)
    insufficient = sum(1 for item in leans if item.status == INSUFFICIENT_DATA)
    if bullish + bearish + neutral == 0:
        overall = INSUFFICIENT_DATA
    elif bullish > bearish and bullish > neutral:
        overall = BULLISH_LEANING
    elif bearish > bullish and bearish > neutral:
        overall = BEARISH_LEANING
    else:
        overall = NEUTRAL
    return ConsensusSummary(bullish, bearish, neutral, insufficient, overall)


def _fingerprint(*, bar_fingerprint: str, indicator_fingerprint: str, oscillator_fingerprint: str, oscillator_leans: tuple[IndicatorLean, ...], moving_averages: tuple[IndicatorLean, ...]) -> str:
    payload = {
        "bar_fingerprint": bar_fingerprint,
        "indicator_fingerprint": indicator_fingerprint,
        "moving_averages": [asdict(item) for item in moving_averages],
        "oscillator_fingerprint": oscillator_fingerprint,
        "oscillators": [asdict(item) for item in oscillator_leans],
        "version": CONSENSUS_VERSION,
    }
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def compute_indicator_consensus(
    *, bars: tuple[MarketBar, ...], indicators: IndicatorSetResult, oscillators: OscillatorSetResult,
) -> IndicatorConsensusResult:
    """Classify each already-computed indicator's latest reading as bullish/bearish
    -leaning or neutral, then count how many lean each way (oversold/overbought
    thresholds for RSI/Stochastic/CCI/Williams %R, MACD-vs-signal crossover,
    ADX-gated +DI/-DI direction, close-vs-EMA position). Mirrors the structure of
    common indicator-consensus panels, with research-safe labels (no buy/sell
    language) -- this is a count of indicator readings, not a trade recommendation.
    """
    if not bars:
        raise ValueError("bars must not be empty")
    last_close = bars[-1].close

    def latest(series_points: tuple) -> float | None:
        return series_points[-1].value if series_points else None

    last_rsi = latest(indicators.rsi.points)
    last_ema = latest(indicators.ema.points)
    last_stochastic_k = latest(oscillators.stochastic_k.points)
    last_cci = latest(oscillators.cci.points)
    last_williams_r = latest(oscillators.williams_r.points)
    last_macd_line = latest(oscillators.macd_line.points)
    last_macd_signal = latest(oscillators.macd_signal.points)
    last_adx = latest(oscillators.adx.points)
    last_plus_di = latest(oscillators.plus_di.points)
    last_minus_di = latest(oscillators.minus_di.points)

    oscillator_leans = (
        _classify_rsi(last_rsi),
        _classify_below_oversold_above_overbought(
            "stochastic_k", last_stochastic_k,
            oversold=STOCHASTIC_OVERSOLD_THRESHOLD, overbought=STOCHASTIC_OVERBOUGHT_THRESHOLD,
        ),
        _classify_below_oversold_above_overbought(
            "cci", last_cci, oversold=CCI_OVERSOLD_THRESHOLD, overbought=CCI_OVERBOUGHT_THRESHOLD,
        ),
        _classify_below_oversold_above_overbought(
            "williams_r", last_williams_r,
            oversold=WILLIAMS_R_OVERSOLD_THRESHOLD, overbought=WILLIAMS_R_OVERBOUGHT_THRESHOLD,
        ),
        _classify_macd(last_macd_line, last_macd_signal),
        _classify_adx(last_adx, last_plus_di, last_minus_di),
    )
    moving_averages = (
        _classify_price_vs_average(f"ema.close.{indicators.ema.period}", last_ema, last_close),
    )

    oscillator_summary = _summarize(oscillator_leans)
    moving_average_summary = _summarize(moving_averages)
    overall_summary = _summarize(oscillator_leans + moving_averages)

    fingerprint = _fingerprint(
        bar_fingerprint=indicators.bar_fingerprint,
        indicator_fingerprint=indicators.fingerprint,
        oscillator_fingerprint=oscillators.fingerprint,
        oscillator_leans=oscillator_leans,
        moving_averages=moving_averages,
    )

    return IndicatorConsensusResult(
        CONSENSUS_VERSION, oscillator_leans, moving_averages,
        oscillator_summary, moving_average_summary, overall_summary,
        fingerprint,
    )
