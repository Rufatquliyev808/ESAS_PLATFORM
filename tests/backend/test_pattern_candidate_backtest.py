from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.retest import RetestObservation, RetestResult
from backend.app.strategies.pattern_candidate_backtest import (
    PatternCandidateBacktestUnsupportedError,
    run_pattern_candidate_backtest,
)


BASE = datetime(2026, 8, 5, tzinfo=UTC)


def _bar(index: int, close: float) -> MarketBar:
    start = BASE + timedelta(minutes=index)
    return MarketBar("GOLD", "M1", start.isoformat(), (start + timedelta(minutes=1)).isoformat(), close, close + 1, close - 1, close, 1, 1, 0.1, 0.1, 0.1, f"e{index}", f"e{index}")


def _retest(observations: tuple[RetestObservation, ...]) -> RetestResult:
    empty = RetestObservation("bullish", "no_retest", None, None, None, None, None, None)
    return RetestResult("1.0.0", 5.0, 0.0, 10.0, 100, observations, empty, empty, "sha256:retest")


def _confirmed(direction: str, observed_at: str, break_at: str = "break") -> RetestObservation:
    return RetestObservation(direction, "confirmed_retest", "BOS", 100.0, break_at, observed_at, observed_at, 5.0)


def test_bullish_and_bearish_returns_use_correct_sign() -> None:
    bars = tuple(_bar(i, 100.0 + i) for i in range(10))
    observations = (_confirmed("bullish", bars[2].end_at), _confirmed("bearish", bars[2].end_at, "break2"))
    retest = _retest(observations)
    bullish = run_pattern_candidate_backtest(
        candidate_id="c1", hypothesis_id="structure_break_long", direction="bullish",
        bars=bars, retest=retest, horizon_bars=3,
    )
    bearish = run_pattern_candidate_backtest(
        candidate_id="c2", hypothesis_id="structure_break_short", direction="bearish",
        bars=bars, retest=retest, horizon_bars=3,
    )
    assert bullish.trades[0].status == "matured"
    assert bullish.trades[0].raw_return_percent > 0
    assert bearish.trades[0].status == "matured"
    assert bearish.trades[0].raw_return_percent < 0
    assert bullish.trades[0].raw_return_percent == pytest.approx(-bearish.trades[0].raw_return_percent)


def test_trade_beyond_dataset_is_immature() -> None:
    bars = tuple(_bar(i, 100.0) for i in range(5))
    retest = _retest((_confirmed("bullish", bars[4].end_at),))
    result = run_pattern_candidate_backtest(
        candidate_id="c1", hypothesis_id="structure_break_long", direction="bullish",
        bars=bars, retest=retest, horizon_bars=3,
    )
    assert result.trades[0].status == "immature"
    assert result.trades[0].exit_price is None
    assert result.matured_events == 0
    assert result.immature_events == 1


def test_unsupported_hypothesis_is_rejected() -> None:
    bars = tuple(_bar(i, 100.0) for i in range(5))
    retest = _retest(())
    with pytest.raises(PatternCandidateBacktestUnsupportedError):
        run_pattern_candidate_backtest(
            candidate_id="c1", hypothesis_id="market_structure_long", direction="bullish",
            bars=bars, retest=retest,
        )


def test_small_sample_is_insufficient_evidence() -> None:
    bars = tuple(_bar(i, 100.0 + (i % 3)) for i in range(20))
    observations = (_confirmed("bullish", bars[0].end_at),)
    retest = _retest(observations)
    result = run_pattern_candidate_backtest(
        candidate_id="c1", hypothesis_id="structure_break_long", direction="bullish",
        bars=bars, retest=retest, horizon_bars=2,
    )
    normal = next(item for item in result.scenarios if item.scenario == "normal")
    assert normal.status == "insufficient_evidence"
    assert normal.reason == "effective_sample_below_30"


def test_large_supportive_sample_produces_positive_confidence_interval() -> None:
    bars = tuple(_bar(i, 100.0 + i * 0.5) for i in range(200))
    observations = tuple(_confirmed("bullish", bars[index].end_at, f"break{index}") for index in range(0, 150, 3))
    retest = _retest(observations)
    result = run_pattern_candidate_backtest(
        candidate_id="c1", hypothesis_id="structure_break_long", direction="bullish",
        bars=bars, retest=retest, horizon_bars=2, spread_bps=0, commission_bps=0, slippage_bps=0, latency_bps=0,
    )
    normal = next(item for item in result.scenarios if item.scenario == "normal")
    assert normal.effective_sample_size >= 30
    assert normal.status == "supportive_evidence"
    assert normal.confidence_interval_low_percent > 0


def test_result_is_deterministic() -> None:
    bars = tuple(_bar(i, 100.0 + i) for i in range(10))
    retest = _retest((_confirmed("bullish", bars[2].end_at),))
    first = run_pattern_candidate_backtest(
        candidate_id="c1", hypothesis_id="structure_break_long", direction="bullish", bars=bars, retest=retest,
    )
    second = run_pattern_candidate_backtest(
        candidate_id="c1", hypothesis_id="structure_break_long", direction="bullish", bars=bars, retest=retest,
    )
    assert first.fingerprint == second.fingerprint
    assert first == second


def test_invalid_cost_and_horizon_parameters_are_rejected() -> None:
    bars = tuple(_bar(i, 100.0) for i in range(5))
    retest = _retest(())
    with pytest.raises(ValueError):
        run_pattern_candidate_backtest(
            candidate_id="c1", hypothesis_id="structure_break_long", direction="bullish",
            bars=bars, retest=retest, horizon_bars=0,
        )
    with pytest.raises(ValueError):
        run_pattern_candidate_backtest(
            candidate_id="c1", hypothesis_id="structure_break_long", direction="bullish",
            bars=bars, retest=retest, spread_bps=-1,
        )
    with pytest.raises(ValueError):
        run_pattern_candidate_backtest(
            candidate_id="c1", hypothesis_id="structure_break_long", direction="bullish",
            bars=bars, retest=retest, adverse_multiplier=3, stress_multiplier=2,
        )
