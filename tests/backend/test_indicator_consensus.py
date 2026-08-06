from backend.app.analysis.bars import MarketBar
from backend.app.analysis.indicator_consensus import (
    BEARISH_LEANING,
    BULLISH_LEANING,
    CONSENSUS_VERSION,
    INSUFFICIENT_DATA,
    NEUTRAL,
    compute_indicator_consensus,
)
from backend.app.analysis.indicators import IndicatorPoint, IndicatorSeries, IndicatorSetResult


def bar(close: float) -> MarketBar:
    return MarketBar(
        symbol="GOLD", timeframe="M1", start_at="2026-08-06T10:00:00.000000",
        end_at="2026-08-06T10:01:00.000000", open=close, high=close, low=close, close=close,
        tick_count=2, tick_volume=2, spread_min=0.1, spread_max=0.1, spread_mean=0.1,
        first_event_id="event:0", last_event_id="event:1",
    )


def indicator_set(*, rsi_value: float | None, ema_value: float | None) -> IndicatorSetResult:
    rsi_point = IndicatorPoint(bar_end_at="2026-08-06T10:01:00.000000", status="ready" if rsi_value is not None else "insufficient_data", value=rsi_value)
    ema_point = IndicatorPoint(bar_end_at="2026-08-06T10:01:00.000000", status="ready" if ema_value is not None else "insufficient_data", value=ema_value)
    rsi = IndicatorSeries(feature_id="rsi.wilder.close", version="1.0.0", period=14, unit="index_0_100", points=(rsi_point,))
    ema = IndicatorSeries(feature_id="ema.close", version="1.0.0", period=20, unit="price", points=(ema_point,))
    atr = IndicatorSeries(feature_id="atr.wilder", version="1.0.0", period=14, unit="price", points=(IndicatorPoint("2026-08-06T10:01:00.000000", "insufficient_data", None),))
    return IndicatorSetResult(ema=ema, rsi=rsi, atr=atr, bar_fingerprint="sha256:bars", fingerprint="sha256:indicators")


def test_oversold_rsi_and_price_above_ema_are_bullish_leaning() -> None:
    result = compute_indicator_consensus(bars=(bar(105.0),), indicators=indicator_set(rsi_value=25.0, ema_value=100.0))
    assert result.version == CONSENSUS_VERSION
    assert result.oscillators[0].status == BULLISH_LEANING
    assert result.moving_averages[0].status == BULLISH_LEANING
    assert result.overall_summary.overall_lean == BULLISH_LEANING
    assert result.overall_summary.bullish_leaning_count == 2
    assert result.interpretation == "research_observation_not_trading_signal"


def test_overbought_rsi_and_price_below_ema_are_bearish_leaning() -> None:
    result = compute_indicator_consensus(bars=(bar(95.0),), indicators=indicator_set(rsi_value=80.0, ema_value=100.0))
    assert result.oscillators[0].status == BEARISH_LEANING
    assert result.moving_averages[0].status == BEARISH_LEANING
    assert result.overall_summary.overall_lean == BEARISH_LEANING
    assert result.overall_summary.bearish_leaning_count == 2


def test_mid_range_rsi_and_price_at_ema_are_neutral() -> None:
    result = compute_indicator_consensus(bars=(bar(100.0),), indicators=indicator_set(rsi_value=50.0, ema_value=100.0))
    assert result.oscillators[0].status == NEUTRAL
    assert result.moving_averages[0].status == NEUTRAL
    assert result.overall_summary.overall_lean == NEUTRAL


def test_missing_indicator_values_are_insufficient_data() -> None:
    result = compute_indicator_consensus(bars=(bar(100.0),), indicators=indicator_set(rsi_value=None, ema_value=None))
    assert result.oscillators[0].status == INSUFFICIENT_DATA
    assert result.moving_averages[0].status == INSUFFICIENT_DATA
    assert result.overall_summary.overall_lean == INSUFFICIENT_DATA
    assert result.overall_summary.insufficient_data_count == 2


def test_mixed_signals_are_neutral_overall() -> None:
    result = compute_indicator_consensus(bars=(bar(105.0),), indicators=indicator_set(rsi_value=80.0, ema_value=100.0))
    assert result.oscillators[0].status == BEARISH_LEANING
    assert result.moving_averages[0].status == BULLISH_LEANING
    assert result.overall_summary.overall_lean == NEUTRAL


def test_rejects_empty_bars() -> None:
    try:
        compute_indicator_consensus(bars=(), indicators=indicator_set(rsi_value=50.0, ema_value=100.0))
    except ValueError as error:
        assert "bars" in str(error)
    else:
        raise AssertionError("expected a ValueError for empty bars")


def test_deterministic_fingerprint_for_same_input() -> None:
    first = compute_indicator_consensus(bars=(bar(105.0),), indicators=indicator_set(rsi_value=25.0, ema_value=100.0))
    second = compute_indicator_consensus(bars=(bar(105.0),), indicators=indicator_set(rsi_value=25.0, ema_value=100.0))
    assert first.fingerprint == second.fingerprint
    third = compute_indicator_consensus(bars=(bar(95.0),), indicators=indicator_set(rsi_value=25.0, ema_value=100.0))
    assert third.fingerprint != first.fingerprint
