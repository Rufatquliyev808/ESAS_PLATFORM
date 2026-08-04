from dataclasses import asdict
from hashlib import sha256
import json
import math

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.indicators import IndicatorSetResult
from backend.app.strategies.contract import (
    EXPERIMENTAL,
    INSUFFICIENT_DATA,
    READY,
    StrategyDefinition,
    StrategyObservation,
    StrategyResult,
    StrategySummary,
)


ABOVE_EMA = "above_ema"
BELOW_EMA = "below_ema"
AT_EMA = "at_ema"

DEFINITION = StrategyDefinition(
    strategy_id="ema_close_relation",
    version="1.0.0",
    lifecycle=EXPERIMENTAL,
    description="Classifies each closed bar close relative to its causal EMA.",
    required_features=("ema.close",),
)


def _normalized(value: str, *, name: str) -> str:
    result = value.strip()
    if not result:
        raise ValueError(f"{name} must not be empty")
    return result


def _result_fingerprint(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def evaluate_ema_close_relation(
    *,
    symbol: str,
    timeframe: str,
    bars: tuple[MarketBar, ...],
    indicators: IndicatorSetResult,
    dataset_fingerprint: str,
) -> StrategyResult:
    """Classify closed bars without producing a trade recommendation."""
    normalized_symbol = _normalized(symbol, name="symbol")
    normalized_timeframe = _normalized(timeframe, name="timeframe")
    normalized_dataset = _normalized(dataset_fingerprint, name="dataset_fingerprint")
    if len(bars) != len(indicators.ema.points):
        raise ValueError("bars and EMA points must have the same length")

    observations: list[StrategyObservation] = []
    counts = {ABOVE_EMA: 0, BELOW_EMA: 0, AT_EMA: 0}
    insufficient = 0

    for bar, point in zip(bars, indicators.ema.points, strict=True):
        if bar.symbol != normalized_symbol or bar.timeframe != normalized_timeframe:
            raise ValueError("bars must match the requested symbol and timeframe")
        if bar.end_at != point.bar_end_at:
            raise ValueError("bars and EMA points must be time-aligned")
        if not math.isfinite(bar.close):
            raise ValueError("bar close must be finite")
        if point.value is None:
            insufficient += 1
            observations.append(StrategyObservation(bar.end_at, INSUFFICIENT_DATA, None, bar.close, None))
            continue
        if not math.isfinite(point.value):
            raise ValueError("EMA value must be finite")
        relation = ABOVE_EMA if bar.close > point.value else BELOW_EMA if bar.close < point.value else AT_EMA
        counts[relation] += 1
        observations.append(StrategyObservation(bar.end_at, READY, relation, bar.close, point.value))

    summary = StrategySummary(
        ready=len(observations) - insufficient,
        insufficient_data=insufficient,
        above=counts[ABOVE_EMA],
        below=counts[BELOW_EMA],
        equal=counts[AT_EMA],
    )
    parameters: tuple[tuple[str, int | float | str], ...] = (("ema_period", indicators.ema.period),)
    payload = {
        "definition": asdict(DEFINITION),
        "symbol": normalized_symbol,
        "timeframe": normalized_timeframe,
        "parameters": parameters,
        "dataset_fingerprint": normalized_dataset,
        "bar_fingerprint": indicators.bar_fingerprint,
        "indicator_fingerprint": indicators.fingerprint,
        "observations": [asdict(item) for item in observations],
        "summary": asdict(summary),
    }
    return StrategyResult(
        definition=DEFINITION,
        symbol=normalized_symbol,
        timeframe=normalized_timeframe,
        parameters=parameters,
        dataset_fingerprint=normalized_dataset,
        bar_fingerprint=indicators.bar_fingerprint,
        indicator_fingerprint=indicators.fingerprint,
        observations=tuple(observations),
        summary=summary,
        fingerprint=_result_fingerprint(payload),
    )
