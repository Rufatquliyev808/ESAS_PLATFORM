from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.liquidity_sweep import LiquiditySweepObservation, LiquiditySweepResult
from backend.app.analysis.market_structure import (
    MarketStructureResult,
    StructureConfirmationObservation,
    StructureSideObservation,
)
from backend.app.analysis.retest import RetestObservation, RetestResult
from backend.app.strategies.pattern_candidate_backtest import (
    PatternCandidateBacktestUnsupportedError,
    run_pattern_candidate_backtest,
)


BASE = datetime(2026, 8, 5, tzinfo=UTC)


def _bar(index: int, close: float) -> MarketBar:
    start = BASE + timedelta(minutes=index)
    return MarketBar("GOLD", "M1", start.isoformat(), (start + timedelta(minutes=1)).isoformat(), close, close + 1, close - 1, close, 1, 1, 0.1, 0.1, 0.1, f"e{index}", f"e{index}")


def _retest(observations: tuple[RetestObservation, ...] = ()) -> RetestResult:
    empty = RetestObservation("bullish", "no_retest", None, None, None, None, None, None)
    return RetestResult("1.0.0", 5.0, 0.0, 10.0, 100, observations, empty, empty, "sha256:retest")


def _confirmed_retest(direction: str, observed_at: str, break_at: str = "break") -> RetestObservation:
    return RetestObservation(direction, "confirmed_retest", "BOS", 100.0, break_at, observed_at, observed_at, 5.0)


def _liquidity(observations: tuple[LiquiditySweepObservation, ...] = ()) -> LiquiditySweepResult:
    empty = LiquiditySweepObservation("bullish", "no_sweep", "sell_side", None, 0, None, None, False)
    return LiquiditySweepResult("1.0.0", 10.0, 2, 1.0, 250, (), observations, empty, empty, "sha256:liquidity")


def _confirmed_sweep(direction: str, observed_at: str) -> LiquiditySweepObservation:
    pool_side = "sell_side" if direction == "bullish" else "buy_side"
    return LiquiditySweepObservation(direction, "confirmed_sweep", pool_side, 100.0, 2, observed_at, 5.0, True)


def _market_structure(observations: tuple[StructureConfirmationObservation, ...] = ()) -> MarketStructureResult:
    empty = StructureSideObservation("long", "insufficient_data", None, None, None)
    return MarketStructureResult("1.0.0", 2, 2, 0.0, 5, (), observations, empty, empty, "sha256:structure")


def _confirmed_structure(direction: str, observed_at: str) -> StructureConfirmationObservation:
    return StructureConfirmationObservation(direction, "confirmed_structure", "HH", "HL", observed_at)


def _run(**overrides):
    defaults = dict(
        candidate_id="c1", hypothesis_id="structure_break_long",
        bars=tuple(_bar(i, 100.0 + i) for i in range(10)),
        retest=_retest(), liquidity_sweep=_liquidity(), market_structure=_market_structure(), horizon_bars=3,
    )
    defaults.update(overrides)
    return run_pattern_candidate_backtest(**defaults)


def test_bullish_and_bearish_returns_use_correct_sign() -> None:
    bars = tuple(_bar(i, 100.0 + i) for i in range(10))
    retest = _retest((
        _confirmed_retest("bullish", bars[2].end_at),
        _confirmed_retest("bearish", bars[2].end_at, "break2"),
    ))
    bullish = _run(candidate_id="c1", hypothesis_id="structure_break_long", bars=bars, retest=retest)
    bearish = _run(candidate_id="c2", hypothesis_id="structure_break_short", bars=bars, retest=retest)
    assert bullish.trades[0].status == "matured"
    assert bullish.trades[0].raw_return_percent > 0
    assert bearish.trades[0].status == "matured"
    assert bearish.trades[0].raw_return_percent < 0
    assert bullish.trades[0].raw_return_percent == pytest.approx(-bearish.trades[0].raw_return_percent)
    assert bullish.direction == "bullish"
    assert bearish.direction == "bearish"


def test_hypothesis_id_determines_direction_not_a_client_supplied_value() -> None:
    """market_structure/hypothesis registry direction vocabulary is long/short;
    this must never leak into the bullish/bearish filter used against
    retest.observations, which is what caused the original bug this test guards."""
    bars = tuple(_bar(i, 100.0 + i) for i in range(10))
    retest = _retest((_confirmed_retest("bullish", bars[2].end_at),))
    result = _run(hypothesis_id="structure_break_long", bars=bars, retest=retest)
    assert result.total_events == 1
    assert result.direction == "bullish"


def test_liquidity_sweep_reclaim_hypotheses_use_liquidity_events() -> None:
    bars = tuple(_bar(i, 100.0 + i) for i in range(10))
    liquidity = _liquidity((
        _confirmed_sweep("bullish", bars[2].end_at),
        _confirmed_sweep("bearish", bars[4].end_at),
    ))
    bullish = _run(hypothesis_id="liquidity_sweep_reclaim_long", bars=bars, liquidity_sweep=liquidity)
    bearish = _run(hypothesis_id="liquidity_sweep_reclaim_short", bars=bars, liquidity_sweep=liquidity)
    assert bullish.total_events == 1
    assert bullish.trades[0].raw_return_percent > 0
    assert bearish.total_events == 1
    assert bearish.trades[0].raw_return_percent < 0


def test_trade_beyond_dataset_is_immature() -> None:
    bars = tuple(_bar(i, 100.0) for i in range(5))
    retest = _retest((_confirmed_retest("bullish", bars[4].end_at),))
    result = _run(bars=bars, retest=retest, horizon_bars=3)
    assert result.trades[0].status == "immature"
    assert result.trades[0].exit_price is None
    assert result.matured_events == 0
    assert result.immature_events == 1


def test_market_structure_hypotheses_use_transition_events() -> None:
    bars = tuple(_bar(i, 100.0 + i) for i in range(10))
    structure = _market_structure((
        _confirmed_structure("bullish", bars[2].end_at),
        _confirmed_structure("bearish", bars[4].end_at),
    ))
    bullish = _run(hypothesis_id="market_structure_long", bars=bars, market_structure=structure)
    bearish = _run(hypothesis_id="market_structure_short", bars=bars, market_structure=structure)
    assert bullish.total_events == 1
    assert bullish.trades[0].raw_return_percent > 0
    assert bearish.total_events == 1
    assert bearish.trades[0].raw_return_percent < 0


def test_unsupported_hypothesis_is_rejected() -> None:
    with pytest.raises(PatternCandidateBacktestUnsupportedError):
        _run(hypothesis_id="fvg_order_block_deferred")


def test_small_sample_is_insufficient_evidence() -> None:
    bars = tuple(_bar(i, 100.0 + (i % 3)) for i in range(20))
    retest = _retest((_confirmed_retest("bullish", bars[0].end_at),))
    result = _run(bars=bars, retest=retest, horizon_bars=2)
    normal = next(item for item in result.scenarios if item.scenario == "normal")
    assert normal.status == "insufficient_evidence"
    assert normal.reason == "effective_sample_below_30"


def test_large_supportive_sample_produces_positive_confidence_interval() -> None:
    bars = tuple(_bar(i, 100.0 + i * 0.5) for i in range(200))
    observations = tuple(_confirmed_retest("bullish", bars[index].end_at, f"break{index}") for index in range(0, 150, 3))
    retest = _retest(observations)
    result = _run(
        bars=bars, retest=retest, horizon_bars=2,
        spread_bps=0, commission_bps=0, slippage_bps=0, latency_bps=0,
    )
    normal = next(item for item in result.scenarios if item.scenario == "normal")
    assert normal.effective_sample_size >= 30
    assert normal.status == "supportive_evidence"
    assert normal.confidence_interval_low_percent > 0


def test_result_is_deterministic() -> None:
    bars = tuple(_bar(i, 100.0 + i) for i in range(10))
    retest = _retest((_confirmed_retest("bullish", bars[2].end_at),))
    first = _run(bars=bars, retest=retest)
    second = _run(bars=bars, retest=retest)
    assert first.fingerprint == second.fingerprint
    assert first == second


def test_invalid_cost_and_horizon_parameters_are_rejected() -> None:
    with pytest.raises(ValueError):
        _run(horizon_bars=0)
    with pytest.raises(ValueError):
        _run(spread_bps=-1)
    with pytest.raises(ValueError):
        _run(adverse_multiplier=3, stress_multiplier=2)
