from dataclasses import asdict
from hashlib import sha256
import json
import math

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.indicators import IndicatorSetResult
from backend.app.strategies.contract import (
    EXPERIMENTAL, INSUFFICIENT_DATA, READY, StrategyDefinition,
    StrategyObservation, StrategyResult, StrategySummary,
)

HIGH_RSI = "high_rsi"
LOW_RSI = "low_rsi"
NEUTRAL_RSI = "neutral_rsi"

DEFINITION = StrategyDefinition(
    strategy_id="rsi_regime_observation",
    version="1.0.0",
    lifecycle=EXPERIMENTAL,
    description="Classifies causal RSI into low, neutral, and high research regimes.",
    required_features=("rsi.close",),
)


def _fingerprint(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def evaluate_rsi_regime_observation(
    *, symbol: str, timeframe: str, bars: tuple[MarketBar, ...],
    indicators: IndicatorSetResult, dataset_fingerprint: str,
    low_threshold: float = 30.0, high_threshold: float = 70.0,
) -> StrategyResult:
    symbol = symbol.strip()
    timeframe = timeframe.strip()
    dataset_fingerprint = dataset_fingerprint.strip()
    if not symbol or not timeframe or not dataset_fingerprint:
        raise ValueError("symbol, timeframe and dataset_fingerprint must not be empty")
    if not (math.isfinite(low_threshold) and math.isfinite(high_threshold)):
        raise ValueError("RSI thresholds must be finite")
    if not 0 <= low_threshold < high_threshold <= 100:
        raise ValueError("RSI thresholds must satisfy 0 <= low < high <= 100")
    if len(bars) != len(indicators.rsi.points):
        raise ValueError("bars and RSI points must have the same length")

    observations: list[StrategyObservation] = []
    counts = {HIGH_RSI: 0, LOW_RSI: 0, NEUTRAL_RSI: 0}
    insufficient = 0
    for bar, point in zip(bars, indicators.rsi.points, strict=True):
        if bar.symbol != symbol or bar.timeframe != timeframe:
            raise ValueError("bars must match the requested symbol and timeframe")
        if bar.end_at != point.bar_end_at:
            raise ValueError("bars and RSI points must be time-aligned")
        if not math.isfinite(bar.close):
            raise ValueError("bar close must be finite")
        if point.value is None:
            insufficient += 1
            observations.append(StrategyObservation(bar.end_at, INSUFFICIENT_DATA, None, bar.close, None))
            continue
        if not math.isfinite(point.value):
            raise ValueError("RSI value must be finite")
        relation = LOW_RSI if point.value <= low_threshold else HIGH_RSI if point.value >= high_threshold else NEUTRAL_RSI
        counts[relation] += 1
        observations.append(StrategyObservation(bar.end_at, READY, relation, bar.close, point.value))

    summary = StrategySummary(
        ready=len(observations) - insufficient,
        insufficient_data=insufficient,
        above=counts[HIGH_RSI], below=counts[LOW_RSI], equal=counts[NEUTRAL_RSI],
    )
    parameters = (("rsi_period", indicators.rsi.period), ("low_threshold", low_threshold),
                  ("high_threshold", high_threshold))
    payload = {
        "definition": asdict(DEFINITION), "symbol": symbol, "timeframe": timeframe,
        "parameters": parameters, "dataset_fingerprint": dataset_fingerprint,
        "bar_fingerprint": indicators.bar_fingerprint,
        "indicator_fingerprint": indicators.fingerprint,
        "observations": [asdict(item) for item in observations], "summary": asdict(summary),
    }
    return StrategyResult(
        definition=DEFINITION, symbol=symbol, timeframe=timeframe, parameters=parameters,
        dataset_fingerprint=dataset_fingerprint, bar_fingerprint=indicators.bar_fingerprint,
        indicator_fingerprint=indicators.fingerprint, observations=tuple(observations),
        summary=summary, fingerprint=_fingerprint(payload),
    )
