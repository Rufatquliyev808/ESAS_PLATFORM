from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.indicators import build_indicator_set
from backend.app.strategies.ema_close_relation import evaluate_ema_close_relation
from backend.app.strategies.outcome_evaluation import (
    IMMATURE, MATURED, NOT_APPLICABLE, evaluate_strategy_outcomes,
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
        spread_mean=0.1, first_event_id=f"event:{index}",
        last_event_id=f"event:{index}",
    )


def strategy(bars: tuple[MarketBar, ...]):
    indicators = build_indicator_set(
        bars, bar_fingerprint="sha256:bars", ema_period=2, rsi_period=2,
        atr_period=2,
    )
    return evaluate_ema_close_relation(
        symbol="GOLD", timeframe="M1", bars=bars, indicators=indicators,
        dataset_fingerprint="sha256:dataset",
    )


def test_future_closed_bar_outcomes_are_measured_after_the_observation() -> None:
    bars = tuple(bar(i, close) for i, close in enumerate([100, 101, 103, 102, 106]))
    result = evaluate_strategy_outcomes(
        strategy=strategy(bars), bars=bars, horizon_bars=2,
    )
    assert [item.status for item in result.observations] == [
        NOT_APPLICABLE, MATURED, MATURED, IMMATURE, IMMATURE,
    ]
    assert result.observations[1].outcome_bar_end_at == bars[3].end_at
    assert result.observations[1].outcome_close == 102
    assert result.observations[1].return_percent == pytest.approx((102 / 101 - 1) * 100)
    assert result.summary.matured == 2
    assert result.summary.immature == 2
    assert result.summary.not_applicable == 1


def test_same_input_produces_same_fingerprint() -> None:
    bars = tuple(bar(i, 100 + i) for i in range(6))
    evaluated = strategy(bars)
    first = evaluate_strategy_outcomes(strategy=evaluated, bars=bars, horizon_bars=1)
    second = evaluate_strategy_outcomes(strategy=evaluated, bars=bars, horizon_bars=1)
    assert first == second
    assert first.fingerprint.startswith("sha256:")
    assert first.interpretation == "historical_outcome_measurement_not_trading_signal"


def test_future_price_labels_outcome_but_does_not_mutate_strategy_observation() -> None:
    bars = tuple(bar(i, 100 + i) for i in range(5))
    evaluated = strategy(bars)
    changed = bars[:-1] + (replace(bars[-1], close=999),)
    original = evaluate_strategy_outcomes(strategy=evaluated, bars=bars, horizon_bars=1)
    revised = evaluate_strategy_outcomes(strategy=evaluated, bars=changed, horizon_bars=1)
    assert evaluated.observations == strategy(bars).observations
    assert original.observations[:-2] == revised.observations[:-2]
    assert original.observations[-2].entry_close == revised.observations[-2].entry_close
    assert original.observations[-2].outcome_close != revised.observations[-2].outcome_close
    assert original.fingerprint != revised.fingerprint


def test_relation_summaries_keep_ema_states_separate() -> None:
    bars = tuple(bar(i, close) for i, close in enumerate([100, 90, 110, 80, 120, 70]))
    result = evaluate_strategy_outcomes(
        strategy=strategy(bars), bars=bars, horizon_bars=1,
    )
    relations = {item.relation for item in result.summary.by_relation}
    assert relations == {"above_ema", "below_ema"}
    assert sum(item.count for item in result.summary.by_relation) == result.summary.matured


@pytest.mark.parametrize("horizon", [0, -1])
def test_invalid_horizon_is_rejected(horizon: int) -> None:
    bars = tuple(bar(i, 100 + i) for i in range(3))
    with pytest.raises(ValueError, match="at least 1"):
        evaluate_strategy_outcomes(
            strategy=strategy(bars), bars=bars, horizon_bars=horizon,
        )


def test_misaligned_bars_are_rejected() -> None:
    bars = tuple(bar(i, 100 + i) for i in range(3))
    misaligned = (replace(bars[0], end_at="2026-08-04T00:00:00+00:00"),) + bars[1:]
    with pytest.raises(ValueError, match="time-aligned"):
        evaluate_strategy_outcomes(
            strategy=strategy(bars), bars=misaligned, horizon_bars=1,
        )
