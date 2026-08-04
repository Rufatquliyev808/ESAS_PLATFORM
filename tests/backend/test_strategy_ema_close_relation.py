from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.indicators import build_indicator_set
from backend.app.strategies import (
    ABOVE_EMA, AT_EMA, EMA_CLOSE_RELATION_DEFINITION, INSUFFICIENT_DATA,
    READY, evaluate_ema_close_relation,
)

BASE_TIME = datetime(2026, 8, 4, 10, 0, tzinfo=UTC)


def bar(index: int, close: float) -> MarketBar:
    start = BASE_TIME + timedelta(minutes=index)
    return MarketBar(
        symbol="GOLD", timeframe="M1",
        start_at=start.isoformat(timespec="microseconds"),
        end_at=(start + timedelta(minutes=1)).isoformat(timespec="microseconds"),
        open=close, high=close, low=close, close=close,
        tick_count=1, tick_volume=1, spread_min=0.1, spread_max=0.1,
        spread_mean=0.1, first_event_id=f"event:{index}", last_event_id=f"event:{index}",
    )


def evaluate(bars: tuple[MarketBar, ...], source: str = "bars"):
    indicators = build_indicator_set(
        bars, bar_fingerprint=f"sha256:{source}",
        ema_period=3, rsi_period=3, atr_period=3,
    )
    return evaluate_ema_close_relation(
        symbol="GOLD", timeframe="M1", bars=bars, indicators=indicators,
        dataset_fingerprint="sha256:dataset",
    )


def test_reference_strategy_is_experimental_and_not_a_signal() -> None:
    assert EMA_CLOSE_RELATION_DEFINITION.lifecycle == "experimental"
    assert EMA_CLOSE_RELATION_DEFINITION.interpretation == "research_observation_not_trading_signal"


def test_warm_up_and_closed_bar_relations_are_explicit() -> None:
    result = evaluate(tuple(bar(i, value) for i, value in enumerate([1, 2, 3, 4])))
    assert [item.status for item in result.observations] == [INSUFFICIENT_DATA, INSUFFICIENT_DATA, READY, READY]
    assert [item.relation for item in result.observations] == [None, None, ABOVE_EMA, ABOVE_EMA]
    assert result.summary.ready == 2
    assert result.summary.insufficient_data == 2


def test_same_inputs_produce_the_same_result_fingerprint() -> None:
    bars = tuple(bar(i, 2) for i in range(4))
    first = evaluate(bars)
    second = evaluate(bars)
    assert first == second
    assert first.fingerprint.startswith("sha256:")
    assert first.observations[-1].relation == AT_EMA


def test_future_bar_does_not_change_past_observations() -> None:
    bars = tuple(bar(i, 100 + i) for i in range(5))
    initial = evaluate(bars, "initial")
    extended = evaluate(bars + (bar(5, 10_000),), "extended")
    assert initial.observations == extended.observations[:-1]
    assert initial.fingerprint != extended.fingerprint


def test_empty_data_has_a_deterministic_empty_result() -> None:
    first = evaluate(())
    assert first == evaluate(())
    assert first.observations == ()
    assert first.summary.ready == 0


def test_rejects_misaligned_indicator_points() -> None:
    bars = tuple(bar(i, 100 + i) for i in range(3))
    indicators = build_indicator_set(bars, bar_fingerprint="sha256:bad", ema_period=3, rsi_period=3, atr_period=3)
    shifted = replace(indicators, ema=replace(indicators.ema, points=indicators.ema.points[::-1]))
    with pytest.raises(ValueError, match="time-aligned"):
        evaluate_ema_close_relation(
            symbol="GOLD", timeframe="M1", bars=bars, indicators=shifted,
            dataset_fingerprint="sha256:dataset",
        )
