import pytest

from backend.app.analysis.indicators import IndicatorPoint, IndicatorSeries, IndicatorSetResult
from backend.app.analysis.liquidity_reaction import CONTINUED, REVERSED, ReactionEvent
from backend.app.analysis.liquidity_reaction_segments import (
    COMPLETED,
    INSUFFICIENT_DATA,
    SEGMENT_VERSION,
    find_indicator_segments,
)
from backend.app.analysis.oscillators import OscillatorPoint, OscillatorSeries, OscillatorSetResult


def _point_series(values: list[float | None], feature_id: str) -> list:
    return [
        IndicatorPoint(bar_end_at=f"t{index}", status="ready" if value is not None else "insufficient_data", value=value)
        for index, value in enumerate(values)
    ]


def indicator_set(rsi_values: list[float | None]) -> IndicatorSetResult:
    rsi = IndicatorSeries(feature_id="rsi.wilder.close", version="1.0.0", period=14, unit="index_0_100", points=tuple(_point_series(rsi_values, "rsi")))
    flat_series = IndicatorSeries(feature_id="ema.close", version="1.0.0", period=20, unit="price", points=tuple(_point_series([None] * len(rsi_values), "ema")))
    return IndicatorSetResult(ema=flat_series, rsi=rsi, atr=flat_series, bar_fingerprint="sha256:bars", fingerprint="sha256:indicators")


def oscillator_set(stochastic_values: list[float | None], adx_values: list[float | None]) -> OscillatorSetResult:
    def series(values: list[float | None], feature_id: str) -> OscillatorSeries:
        points = tuple(
            OscillatorPoint(bar_end_at=f"t{index}", status="ready" if value is not None else "insufficient_data", value=value)
            for index, value in enumerate(values)
        )
        return OscillatorSeries(feature_id=feature_id, version="1.0.0", period=14, unit="index", points=points)
    empty = series([None] * len(stochastic_values), "unused")
    return OscillatorSetResult(
        stochastic_k=series(stochastic_values, "stochastic.k"), cci=empty, adx=series(adx_values, "adx.wilder"),
        plus_di=empty, minus_di=empty, macd_line=empty, macd_signal=empty, williams_r=empty,
        bar_fingerprint="sha256:bars", fingerprint="sha256:oscillators",
    )


def _events(count_oversold: int, count_neutral: int) -> tuple[ReactionEvent, ...]:
    events = []
    for index in range(count_oversold):
        events.append(ReactionEvent("buy_side", 100.0, f"t{index}", index, REVERSED, 50.0))
    for offset in range(count_neutral):
        index = count_oversold + offset
        events.append(ReactionEvent("buy_side", 100.0, f"t{index}", index, CONTINUED, 50.0))
    return tuple(events)


def test_rsi_oversold_segment_exceeds_baseline_when_it_reverses_more_often() -> None:
    events = _events(30, 30)
    rsi_values = [20.0] * 30 + [50.0] * 30
    stochastic_values = [50.0] * 60
    adx_values = [10.0] * 60
    result = find_indicator_segments(
        events, "buy_side",
        indicators=indicator_set(rsi_values),
        oscillators=oscillator_set(stochastic_values, adx_values),
    )
    assert result.version == SEGMENT_VERSION
    assert result.pool_side == "buy_side"
    assert result.trial_count == 5
    assert result.baseline.status == COMPLETED
    assert result.baseline.reversed_percent == pytest.approx(50.0)

    by_id = {item.condition_id: item for item in result.segments}
    oversold = by_id["rsi_oversold"]
    assert oversold.status == COMPLETED
    assert oversold.n_total == 30
    assert oversold.reversed_percent == pytest.approx(100.0)
    assert oversold.exceeds_baseline is True
    assert oversold.confidence_interval_low_percent > result.baseline.reversed_percent

    overbought = by_id["rsi_overbought"]
    assert overbought.status == INSUFFICIENT_DATA
    assert overbought.n_total == 0
    assert overbought.exceeds_baseline is None


def test_segments_below_minimum_sample_are_insufficient_data() -> None:
    events = _events(10, 10)
    rsi_values = [20.0] * 10 + [50.0] * 10
    stochastic_values = [50.0] * 20
    adx_values = [10.0] * 20
    result = find_indicator_segments(
        events, "buy_side",
        indicators=indicator_set(rsi_values),
        oscillators=oscillator_set(stochastic_values, adx_values),
    )
    assert result.baseline.status == INSUFFICIENT_DATA
    for segment in result.segments:
        assert segment.status == INSUFFICIENT_DATA


def test_missing_pool_side_events_yield_insufficient_baseline() -> None:
    events = _events(30, 30)
    rsi_values = [20.0] * 60
    stochastic_values = [50.0] * 60
    adx_values = [10.0] * 60
    result = find_indicator_segments(
        events, "sell_side",
        indicators=indicator_set(rsi_values),
        oscillators=oscillator_set(stochastic_values, adx_values),
    )
    assert result.baseline.status == INSUFFICIENT_DATA
    assert result.baseline.n_total == 0


def test_rejects_unsafe_confidence_level() -> None:
    events = _events(5, 5)
    rsi_values = [20.0] * 10
    stochastic_values = [50.0] * 10
    adx_values = [10.0] * 10
    with pytest.raises(ValueError, match="confidence_level_percent"):
        find_indicator_segments(
            events, "buy_side",
            indicators=indicator_set(rsi_values),
            oscillators=oscillator_set(stochastic_values, adx_values),
            confidence_level_percent=100.0,
        )


def test_deterministic_fingerprint_for_same_input() -> None:
    events = _events(30, 30)
    rsi_values = [20.0] * 30 + [50.0] * 30
    stochastic_values = [50.0] * 60
    adx_values = [10.0] * 60
    first = find_indicator_segments(
        events, "buy_side", indicators=indicator_set(rsi_values),
        oscillators=oscillator_set(stochastic_values, adx_values),
    )
    second = find_indicator_segments(
        events, "buy_side", indicators=indicator_set(rsi_values),
        oscillators=oscillator_set(stochastic_values, adx_values),
    )
    assert first.fingerprint == second.fingerprint
