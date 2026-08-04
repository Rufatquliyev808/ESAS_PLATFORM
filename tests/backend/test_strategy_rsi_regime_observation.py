from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.indicators import build_indicator_set
from backend.app.strategies import (
    HIGH_RSI, LOW_RSI, NEUTRAL_RSI, INSUFFICIENT_DATA, READY,
    RSI_REGIME_OBSERVATION_DEFINITION, evaluate_rsi_regime_observation,
)

BASE_TIME = datetime(2026, 8, 4, 10, 0, tzinfo=UTC)


def bar(index: int, close: float) -> MarketBar:
    start = BASE_TIME + timedelta(minutes=index)
    return MarketBar(
        symbol="GOLD", timeframe="M1", start_at=start.isoformat(timespec="microseconds"),
        end_at=(start + timedelta(minutes=1)).isoformat(timespec="microseconds"),
        open=close, high=close, low=close, close=close, tick_count=1, tick_volume=1,
        spread_min=.1, spread_max=.1, spread_mean=.1,
        first_event_id=f"event:{index}", last_event_id=f"event:{index}",
    )


def indicators(bars):
    return build_indicator_set(bars, bar_fingerprint="sha256:bars", ema_period=2,
                               rsi_period=2, atr_period=2)


def evaluate(bars):
    return evaluate_rsi_regime_observation(
        symbol="GOLD", timeframe="M1", bars=bars, indicators=indicators(bars),
        dataset_fingerprint="sha256:dataset", low_threshold=30, high_threshold=70,
    )


def test_definition_is_independent_experimental_observation() -> None:
    assert RSI_REGIME_OBSERVATION_DEFINITION.strategy_id == "rsi_regime_observation"
    assert RSI_REGIME_OBSERVATION_DEFINITION.lifecycle == "experimental"
    assert RSI_REGIME_OBSERVATION_DEFINITION.interpretation == "research_observation_not_trading_signal"


def test_warm_up_and_regimes_are_explicit_and_deterministic() -> None:
    bars = tuple(bar(i, value) for i, value in enumerate([1, 2, 1, 2, 1]))
    first = evaluate(bars)
    assert first == evaluate(bars)
    assert first.observations[0].status == INSUFFICIENT_DATA
    assert all(item.status == READY for item in first.observations[2:])
    assert {item.relation for item in first.observations[2:]} <= {HIGH_RSI, LOW_RSI, NEUTRAL_RSI}


def test_threshold_boundaries_are_inclusive() -> None:
    bars = (bar(0, 1), bar(1, 2), bar(2, 3))
    source = indicators(bars)
    points = list(source.rsi.points)
    points[1] = replace(points[1], value=30.0, status=READY)
    points[2] = replace(points[2], value=70.0, status=READY)
    source = replace(source, rsi=replace(source.rsi, points=tuple(points)))
    result = evaluate_rsi_regime_observation(
        symbol="GOLD", timeframe="M1", bars=bars, indicators=source,
        dataset_fingerprint="sha256:dataset", low_threshold=30, high_threshold=70,
    )
    assert result.observations[1].relation == LOW_RSI
    assert result.observations[2].relation == HIGH_RSI


def test_future_bar_does_not_change_past_observations() -> None:
    bars = tuple(bar(i, 100 + i) for i in range(5))
    assert evaluate(bars).observations == evaluate(bars + (bar(5, 10_000),)).observations[:-1]


@pytest.mark.parametrize("low,high", [(70, 30), (30, 30), (-1, 70), (30, 101)])
def test_invalid_thresholds_are_rejected(low: float, high: float) -> None:
    with pytest.raises(ValueError, match="0 <= low < high <= 100"):
        evaluate_rsi_regime_observation(
            symbol="GOLD", timeframe="M1", bars=(), indicators=indicators(()),
            dataset_fingerprint="sha256:dataset", low_threshold=low, high_threshold=high,
        )
