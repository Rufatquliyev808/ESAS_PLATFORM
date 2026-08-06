from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.indicators import IndicatorPoint, IndicatorSeries
from backend.app.analysis.liquidity_sweep import LiquiditySweepObservation, LiquiditySweepResult
from backend.app.analysis.market_structure import (
    MarketStructureResult,
    StructureConfirmationObservation,
    StructureSideObservation,
)
from backend.app.analysis.retest import RetestObservation, RetestResult
from backend.app.strategies.pattern_candidate_backtest import (
    PatternCandidateBacktestUnsupportedError,
    bonferroni_corrected_scenario,
    classify_backtest_verdict,
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


def test_classify_backtest_verdict_maps_status_and_reason() -> None:
    assert classify_backtest_verdict(status="supportive_evidence", reason="ci_entirely_above_zero_baseline") == "accepted_for_shadow"
    assert classify_backtest_verdict(status="insufficient_evidence", reason="effective_sample_below_30") == "insufficient_evidence"
    assert classify_backtest_verdict(status="insufficient_evidence", reason="ci_crosses_or_is_below_zero_baseline") == "rejected"
    assert classify_backtest_verdict(status="insufficient_evidence", reason="no_matured_trades") == "rejected"
    assert classify_backtest_verdict(status="insufficient_evidence", reason="zero_sample_variance") == "rejected"


def test_invalid_cost_and_horizon_parameters_are_rejected() -> None:
    with pytest.raises(ValueError):
        _run(horizon_bars=0)
    with pytest.raises(ValueError):
        _run(spread_bps=-1)


def _supportive_normal_scenario() -> dict[str, object]:
    bars = tuple(_bar(i, 100.0 + i * 0.5) for i in range(200))
    observations = tuple(_confirmed_retest("bullish", bars[index].end_at, f"break{index}") for index in range(0, 150, 3))
    retest = _retest(observations)
    result = _run(
        bars=bars, retest=retest, horizon_bars=2,
        spread_bps=0, commission_bps=0, slippage_bps=0, latency_bps=0,
    )
    normal = next(item for item in result.scenarios if item.scenario == "normal")
    assert normal.status == "supportive_evidence"
    return asdict(normal)


def test_bonferroni_correction_is_near_identity_at_family_trial_count_one() -> None:
    scenario = _supportive_normal_scenario()
    corrected = bonferroni_corrected_scenario(scenario, family_trial_count=1)
    assert corrected["status"] == "supportive_evidence"
    assert corrected["confidence_interval_low_percent"] == pytest.approx(
        scenario["confidence_interval_low_percent"], abs=1e-3,
    )
    assert corrected["family_trial_count"] == 1
    assert corrected["alpha_corrected"] == pytest.approx(0.05)


def _borderline_supportive_scenario() -> dict[str, object]:
    # mean=1.0, stdev=5.0, n=100 -> margin(z) = z * 0.5. At the flat (m=1)
    # z~1.96 the CI barely clears zero (low ~= 0.02); by m=5 the corrected z
    # (~2.576) pushes the margin past the mean and the CI crosses zero.
    return {
        "scenario": "normal", "status": "supportive_evidence", "reason": "ci_entirely_above_zero_baseline",
        "effective_sample_size": 100, "net_mean_return_percent": 1.0,
        "sample_standard_deviation": 5.0, "confidence_interval_low_percent": 0.02,
        "confidence_interval_high_percent": 1.98,
    }


def test_bonferroni_correction_widens_ci_and_can_flip_verdict_as_family_grows() -> None:
    scenario = _borderline_supportive_scenario()
    previous_low = bonferroni_corrected_scenario(scenario, family_trial_count=1)["confidence_interval_low_percent"]
    flipped_to_insufficient = False
    for family_trial_count in (1, 5, 20, 100, 1_000):
        corrected = bonferroni_corrected_scenario(scenario, family_trial_count=family_trial_count)
        # The corrected interval only ever widens (lower bound moves down)
        # as the family grows -- a stricter bar can never loosen evidence.
        assert corrected["confidence_interval_low_percent"] <= previous_low + 1e-9
        previous_low = corrected["confidence_interval_low_percent"]
        if corrected["status"] == "insufficient_evidence":
            flipped_to_insufficient = True
            assert corrected["reason"] == "multiple_testing_correction_ci_crosses_or_is_below_zero_baseline"
            assert classify_backtest_verdict(status=corrected["status"], reason=corrected["reason"]) == "rejected"
    assert flipped_to_insufficient, "expected a large enough family to push the CI below zero"


def test_bonferroni_correction_leaves_an_insufficient_scenario_unchanged() -> None:
    scenario = {
        "scenario": "normal", "status": "insufficient_evidence", "reason": "effective_sample_below_30",
        "effective_sample_size": 5, "net_mean_return_percent": 0.1,
        "sample_standard_deviation": None, "confidence_interval_low_percent": None,
        "confidence_interval_high_percent": None,
    }
    corrected = bonferroni_corrected_scenario(scenario, family_trial_count=10)
    assert corrected == scenario
    assert corrected is not scenario


def test_scenario_includes_random_timing_baseline_fields() -> None:
    bars = tuple(_bar(i, 100.0 + i * 0.5) for i in range(200))
    observations = tuple(_confirmed_retest("bullish", bars[index].end_at, f"break{index}") for index in range(0, 150, 3))
    retest = _retest(observations)
    result = _run(
        bars=bars, retest=retest, horizon_bars=2,
        spread_bps=0, commission_bps=0, slippage_bps=0, latency_bps=0,
    )
    normal = next(item for item in result.scenarios if item.scenario == "normal")
    assert normal.random_timing_baseline_sample_size > 0
    assert normal.random_timing_baseline_mean_return_percent is not None
    assert normal.beats_random_timing_baseline is not None


def test_random_timing_baseline_is_deterministic_for_same_inputs() -> None:
    bars = tuple(_bar(i, 100.0 + i * 0.5) for i in range(200))
    observations = tuple(_confirmed_retest("bullish", bars[index].end_at, f"break{index}") for index in range(0, 150, 3))
    retest = _retest(observations)
    first = _run(bars=bars, retest=retest, horizon_bars=2)
    second = _run(bars=bars, retest=retest, horizon_bars=2)
    normal_first = next(item for item in first.scenarios if item.scenario == "normal")
    normal_second = next(item for item in second.scenarios if item.scenario == "normal")
    assert normal_first.random_timing_baseline_mean_return_percent == normal_second.random_timing_baseline_mean_return_percent


def test_candidate_rejected_when_it_underperforms_random_timing_baseline() -> None:
    # A steep, uniform uptrend where the real triggers cluster late in the
    # series (high price base -> small percentage move) while the
    # random-timing sample draws from the whole series (including the early,
    # low price base, high percentage move region). The candidate clears the
    # flat zero baseline easily but is actually worse than a hypothesis-blind
    # random entry over the same period.
    bars = tuple(_bar(i, 100.0 + i) for i in range(300))
    observations = tuple(_confirmed_retest("bullish", bars[index].end_at, f"break{index}") for index in range(250, 290))
    retest = _retest(observations)
    result = _run(
        bars=bars, retest=retest, horizon_bars=2,
        spread_bps=0, commission_bps=0, slippage_bps=0, latency_bps=0,
    )
    normal = next(item for item in result.scenarios if item.scenario == "normal")
    assert normal.effective_sample_size >= 30
    assert normal.confidence_interval_low_percent > 0
    assert normal.beats_random_timing_baseline is False
    assert normal.status == "insufficient_evidence"
    assert normal.reason == "ci_does_not_exceed_random_timing_baseline"
    assert classify_backtest_verdict(status=normal.status, reason=normal.reason) == "rejected"


def _flat_rsi_series(bars: tuple[MarketBar, ...]) -> IndicatorSeries:
    points = tuple(IndicatorPoint(bar.end_at, "ready", 50.0) for bar in bars)
    return IndicatorSeries("rsi.close", "1.0.0", 14, "index", points)


def test_scenario_includes_single_feature_baseline_fields() -> None:
    bars = tuple(_bar(i, 100.0 + i * 0.5) for i in range(200))
    observations = tuple(_confirmed_retest("bullish", bars[index].end_at, f"break{index}") for index in range(0, 150, 3))
    retest = _retest(observations)
    result = _run(
        bars=bars, retest=retest, horizon_bars=2, rsi=_flat_rsi_series(bars),
        spread_bps=0, commission_bps=0, slippage_bps=0, latency_bps=0,
    )
    normal = next(item for item in result.scenarios if item.scenario == "normal")
    # A flat RSI series never crosses the oversold/overbought thresholds, so
    # the baseline is present but empty -- this must not block acceptance.
    assert normal.single_feature_baseline_sample_size == 0
    assert normal.single_feature_baseline_mean_return_percent is None
    assert normal.beats_single_feature_baseline is None


def test_single_feature_baseline_is_skipped_without_rsi_data() -> None:
    bars = tuple(_bar(i, 100.0 + i) for i in range(50))
    result = _run(bars=bars, horizon_bars=2)
    normal = next(item for item in result.scenarios if item.scenario == "normal")
    assert normal.single_feature_baseline_sample_size == 0
    assert normal.single_feature_baseline_mean_return_percent is None
    assert normal.beats_single_feature_baseline is None


def test_candidate_rejected_when_it_underperforms_single_feature_baseline_but_beats_random_timing() -> None:
    # Same steep uptrend idea as the random-timing test, but the real trades
    # cluster in a moderately favorable early region (beats the broad
    # random-timing sample) while the single-feature RSI rule's crossings
    # are placed even earlier (the very lowest price base -> very high
    # percentage return), so only the single-feature baseline check fails.
    bars = tuple(_bar(i, 100.0 + i) for i in range(300))
    observations = tuple(_confirmed_retest("bullish", bars[index].end_at, f"break{index}") for index in range(50, 90))
    retest = _retest(observations)

    rsi_values = [50.0] * 300
    for index in range(0, 21):
        rsi_values[index] = 20.0 if index % 2 == 0 else 40.0
    points = tuple(IndicatorPoint(bars[index].end_at, "ready", rsi_values[index]) for index in range(300))
    rsi = IndicatorSeries("rsi.close", "1.0.0", 14, "index", points)

    result = _run(
        bars=bars, retest=retest, horizon_bars=2, rsi=rsi,
        spread_bps=0, commission_bps=0, slippage_bps=0, latency_bps=0,
    )
    normal = next(item for item in result.scenarios if item.scenario == "normal")
    assert normal.effective_sample_size >= 30
    assert normal.confidence_interval_low_percent > 0
    assert normal.beats_random_timing_baseline is True
    assert normal.single_feature_baseline_sample_size > 0
    assert normal.beats_single_feature_baseline is False
    assert normal.status == "insufficient_evidence"
    assert normal.reason == "ci_does_not_exceed_single_feature_baseline"
    assert classify_backtest_verdict(status=normal.status, reason=normal.reason) == "rejected"


def test_bonferroni_correction_can_fail_via_baseline_even_when_still_clearing_zero() -> None:
    scenario = {
        "scenario": "normal", "status": "supportive_evidence", "reason": "ci_entirely_above_zero_baseline",
        "effective_sample_size": 100, "net_mean_return_percent": 2.0,
        "sample_standard_deviation": 5.0, "confidence_interval_low_percent": 1.02,
        "confidence_interval_high_percent": 2.98,
        "random_timing_baseline_mean_return_percent": 0.5,
    }
    at_m1 = bonferroni_corrected_scenario(scenario, family_trial_count=1)
    assert at_m1["status"] == "supportive_evidence"
    assert at_m1["beats_random_timing_baseline"] is True

    at_m100 = bonferroni_corrected_scenario(scenario, family_trial_count=100)
    assert at_m100["confidence_interval_low_percent"] > 0
    assert at_m100["beats_random_timing_baseline"] is False
    assert at_m100["status"] == "insufficient_evidence"
    assert at_m100["reason"] == "multiple_testing_correction_ci_does_not_exceed_random_timing_baseline"
    assert classify_backtest_verdict(status=at_m100["status"], reason=at_m100["reason"]) == "rejected"


def test_bonferroni_correction_can_fail_via_single_feature_baseline_specifically() -> None:
    scenario = {
        "scenario": "normal", "status": "supportive_evidence", "reason": "ci_entirely_above_zero_baseline",
        "effective_sample_size": 100, "net_mean_return_percent": 2.0,
        "sample_standard_deviation": 5.0, "confidence_interval_low_percent": 1.02,
        "confidence_interval_high_percent": 2.98,
        "random_timing_baseline_mean_return_percent": -1.0,
        "single_feature_baseline_mean_return_percent": 0.5,
    }
    at_m1 = bonferroni_corrected_scenario(scenario, family_trial_count=1)
    assert at_m1["status"] == "supportive_evidence"
    assert at_m1["beats_random_timing_baseline"] is True
    assert at_m1["beats_single_feature_baseline"] is True

    at_m100 = bonferroni_corrected_scenario(scenario, family_trial_count=100)
    assert at_m100["confidence_interval_low_percent"] > 0
    assert at_m100["beats_random_timing_baseline"] is True
    assert at_m100["beats_single_feature_baseline"] is False
    assert at_m100["status"] == "insufficient_evidence"
    assert at_m100["reason"] == "multiple_testing_correction_ci_does_not_exceed_single_feature_baseline"
    assert classify_backtest_verdict(status=at_m100["status"], reason=at_m100["reason"]) == "rejected"


def test_bonferroni_correction_rejects_invalid_inputs() -> None:
    scenario = _supportive_normal_scenario()
    with pytest.raises(ValueError):
        bonferroni_corrected_scenario(scenario, family_trial_count=0)
    with pytest.raises(ValueError):
        bonferroni_corrected_scenario(scenario, family_trial_count=1, family_wise_alpha=0)
    with pytest.raises(ValueError):
        bonferroni_corrected_scenario(scenario, family_trial_count=1, family_wise_alpha=1)
    with pytest.raises(ValueError):
        _run(adverse_multiplier=3, stress_multiplier=2)
