from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.indicators import IndicatorSetResult


CONSENSUS_VERSION = "1.0.0"
BULLISH_LEANING = "bullish_leaning"
BEARISH_LEANING = "bearish_leaning"
NEUTRAL = "neutral"
INSUFFICIENT_DATA = "insufficient_data"
RSI_OVERSOLD_THRESHOLD = 30.0
RSI_OVERBOUGHT_THRESHOLD = 70.0


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
    if value is None:
        return IndicatorLean("rsi", INSUFFICIENT_DATA, None, None)
    if value < RSI_OVERSOLD_THRESHOLD:
        return IndicatorLean("rsi", BULLISH_LEANING, value, RSI_OVERSOLD_THRESHOLD)
    if value > RSI_OVERBOUGHT_THRESHOLD:
        return IndicatorLean("rsi", BEARISH_LEANING, value, RSI_OVERBOUGHT_THRESHOLD)
    return IndicatorLean("rsi", NEUTRAL, value, None)


def _classify_price_vs_average(indicator_id: str, average: float | None, close: float) -> IndicatorLean:
    if average is None:
        return IndicatorLean(indicator_id, INSUFFICIENT_DATA, None, close)
    if close > average:
        return IndicatorLean(indicator_id, BULLISH_LEANING, average, close)
    if close < average:
        return IndicatorLean(indicator_id, BEARISH_LEANING, average, close)
    return IndicatorLean(indicator_id, NEUTRAL, average, close)


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


def _fingerprint(*, bar_fingerprint: str, indicator_fingerprint: str, oscillators: tuple[IndicatorLean, ...], moving_averages: tuple[IndicatorLean, ...]) -> str:
    payload = {
        "bar_fingerprint": bar_fingerprint,
        "indicator_fingerprint": indicator_fingerprint,
        "moving_averages": [asdict(item) for item in moving_averages],
        "oscillators": [asdict(item) for item in oscillators],
        "version": CONSENSUS_VERSION,
    }
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def compute_indicator_consensus(
    *, bars: tuple[MarketBar, ...], indicators: IndicatorSetResult,
) -> IndicatorConsensusResult:
    """Classify each already-computed indicator's latest reading as bullish/bearish
    -leaning or neutral, then count how many lean each way (RSI oversold/overbought
    threshold, close-vs-EMA position). Mirrors the structure of common indicator
    -consensus panels, at a smaller indicator count and with research-safe labels
    (no buy/sell language) -- this is a count of indicator readings, not a trade
    recommendation.
    """
    if not bars:
        raise ValueError("bars must not be empty")
    last_close = bars[-1].close
    last_rsi = indicators.rsi.points[-1].value if indicators.rsi.points else None
    last_ema = indicators.ema.points[-1].value if indicators.ema.points else None

    oscillators = (_classify_rsi(last_rsi),)
    moving_averages = (
        _classify_price_vs_average(f"ema.close.{indicators.ema.period}", last_ema, last_close),
    )

    oscillator_summary = _summarize(oscillators)
    moving_average_summary = _summarize(moving_averages)
    overall_summary = _summarize(oscillators + moving_averages)

    fingerprint = _fingerprint(
        bar_fingerprint=indicators.bar_fingerprint,
        indicator_fingerprint=indicators.fingerprint,
        oscillators=oscillators,
        moving_averages=moving_averages,
    )

    return IndicatorConsensusResult(
        CONSENSUS_VERSION, oscillators, moving_averages,
        oscillator_summary, moving_average_summary, overall_summary,
        fingerprint,
    )
