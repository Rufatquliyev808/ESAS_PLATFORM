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
from backend.app.analysis.oscillators import OscillatorPoint, OscillatorSeries, OscillatorSetResult


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


def _oscillator_series(feature_id: str, period: int, value: float | None) -> OscillatorSeries:
    point = OscillatorPoint(
        bar_end_at="2026-08-06T10:01:00.000000",
        status="ready" if value is not None else "insufficient_data",
        value=value,
    )
    return OscillatorSeries(feature_id=feature_id, version="1.0.0", period=period, unit="index", points=(point,))


def oscillator_set(
    *, stochastic_k: float | None = None, cci: float | None = None, williams_r: float | None = None,
    macd_line: float | None = None, macd_signal: float | None = None,
    adx: float | None = None, plus_di: float | None = None, minus_di: float | None = None,
) -> OscillatorSetResult:
    return OscillatorSetResult(
        stochastic_k=_oscillator_series("stochastic.k", 14, stochastic_k),
        cci=_oscillator_series("cci", 20, cci),
        adx=_oscillator_series("adx.wilder", 14, adx),
        plus_di=_oscillator_series("di.plus", 14, plus_di),
        minus_di=_oscillator_series("di.minus", 14, minus_di),
        macd_line=_oscillator_series("macd.line", 26, macd_line),
        macd_signal=_oscillator_series("macd.signal", 9, macd_signal),
        williams_r=_oscillator_series("williams.r", 14, williams_r),
        bar_fingerprint="sha256:bars", fingerprint="sha256:oscillators",
    )


def test_oversold_rsi_and_price_above_ema_are_bullish_leaning() -> None:
    result = compute_indicator_consensus(
        bars=(bar(105.0),), indicators=indicator_set(rsi_value=25.0, ema_value=100.0),
        oscillators=oscillator_set(),
    )
    assert result.version == CONSENSUS_VERSION
    assert result.oscillators[0].indicator_id == "rsi"
    assert result.oscillators[0].status == BULLISH_LEANING
    assert result.moving_averages[0].status == BULLISH_LEANING
    assert result.overall_summary.overall_lean == BULLISH_LEANING
    assert result.overall_summary.bullish_leaning_count == 2
    assert result.interpretation == "research_observation_not_trading_signal"


def test_overbought_rsi_and_price_below_ema_are_bearish_leaning() -> None:
    result = compute_indicator_consensus(
        bars=(bar(95.0),), indicators=indicator_set(rsi_value=80.0, ema_value=100.0),
        oscillators=oscillator_set(),
    )
    assert result.oscillators[0].status == BEARISH_LEANING
    assert result.moving_averages[0].status == BEARISH_LEANING
    assert result.overall_summary.overall_lean == BEARISH_LEANING
    assert result.overall_summary.bearish_leaning_count == 2


def test_mid_range_rsi_and_price_at_ema_are_neutral() -> None:
    result = compute_indicator_consensus(
        bars=(bar(100.0),), indicators=indicator_set(rsi_value=50.0, ema_value=100.0),
        oscillators=oscillator_set(),
    )
    assert result.oscillators[0].status == NEUTRAL
    assert result.moving_averages[0].status == NEUTRAL
    assert result.overall_summary.overall_lean == NEUTRAL


def test_missing_indicator_values_are_insufficient_data() -> None:
    result = compute_indicator_consensus(
        bars=(bar(100.0),), indicators=indicator_set(rsi_value=None, ema_value=None),
        oscillators=oscillator_set(),
    )
    assert result.oscillators[0].status == INSUFFICIENT_DATA
    assert result.moving_averages[0].status == INSUFFICIENT_DATA
    assert result.overall_summary.overall_lean == INSUFFICIENT_DATA
    assert result.overall_summary.insufficient_data_count == 7
    assert len(result.oscillators) == 6


def test_mixed_signals_are_neutral_overall() -> None:
    result = compute_indicator_consensus(
        bars=(bar(105.0),), indicators=indicator_set(rsi_value=80.0, ema_value=100.0),
        oscillators=oscillator_set(),
    )
    assert result.oscillators[0].status == BEARISH_LEANING
    assert result.moving_averages[0].status == BULLISH_LEANING
    assert result.overall_summary.overall_lean == NEUTRAL


def test_oscillator_set_covers_all_six_oscillators_in_order() -> None:
    result = compute_indicator_consensus(
        bars=(bar(100.0),), indicators=indicator_set(rsi_value=50.0, ema_value=100.0),
        oscillators=oscillator_set(
            stochastic_k=10.0, cci=-150.0, williams_r=-90.0,
            macd_line=1.0, macd_signal=0.5, adx=30.0, plus_di=25.0, minus_di=10.0,
        ),
    )
    assert [item.indicator_id for item in result.oscillators] == [
        "rsi", "stochastic_k", "cci", "williams_r", "macd", "adx",
    ]
    assert result.oscillators[1].status == BULLISH_LEANING  # stochastic_k=10 < 20 oversold
    assert result.oscillators[2].status == BULLISH_LEANING  # cci=-150 < -100 oversold
    assert result.oscillators[3].status == BULLISH_LEANING  # williams_r=-90 < -80 oversold
    assert result.oscillators[4].status == BULLISH_LEANING  # macd(1.0) > signal(0.5)
    assert result.oscillators[5].status == BULLISH_LEANING  # adx>25 and +DI>-DI


def test_macd_bearish_crossover_and_weak_adx_trend_is_neutral() -> None:
    result = compute_indicator_consensus(
        bars=(bar(100.0),), indicators=indicator_set(rsi_value=50.0, ema_value=100.0),
        oscillators=oscillator_set(
            macd_line=0.2, macd_signal=0.8, adx=10.0, plus_di=25.0, minus_di=10.0,
        ),
    )
    assert result.oscillators[4].status == BEARISH_LEANING  # macd(0.2) < signal(0.8)
    assert result.oscillators[5].status == NEUTRAL  # adx=10 below trending threshold


def test_rejects_empty_bars() -> None:
    try:
        compute_indicator_consensus(
            bars=(), indicators=indicator_set(rsi_value=50.0, ema_value=100.0),
            oscillators=oscillator_set(),
        )
    except ValueError as error:
        assert "bars" in str(error)
    else:
        raise AssertionError("expected a ValueError for empty bars")


def test_deterministic_fingerprint_for_same_input() -> None:
    first = compute_indicator_consensus(
        bars=(bar(105.0),), indicators=indicator_set(rsi_value=25.0, ema_value=100.0),
        oscillators=oscillator_set(),
    )
    second = compute_indicator_consensus(
        bars=(bar(105.0),), indicators=indicator_set(rsi_value=25.0, ema_value=100.0),
        oscillators=oscillator_set(),
    )
    assert first.fingerprint == second.fingerprint
    third = compute_indicator_consensus(
        bars=(bar(95.0),), indicators=indicator_set(rsi_value=25.0, ema_value=100.0),
        oscillators=oscillator_set(),
    )
    assert third.fingerprint != first.fingerprint
