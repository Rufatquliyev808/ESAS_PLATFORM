from dataclasses import replace

import pytest

from backend.app.analysis.bos_choch import BosChochResult, StructureBreakObservation
from backend.app.analysis.liquidity_sweep import LiquiditySweepResult, LiquiditySweepObservation
from backend.app.analysis.market_structure import MarketStructureResult, StructureSideObservation
from backend.app.analysis.retest import RetestResult, RetestObservation
from backend.app.strategies.pattern_candidate import detect_pattern_candidates


def _structure(long_state: str = "confirmed_structure", short_state: str = "insufficient_data") -> MarketStructureResult:
    long_obs = StructureSideObservation(
        "long", long_state,
        "HH" if long_state == "confirmed_structure" else None,
        "HL" if long_state == "confirmed_structure" else None,
        "2026-08-05T00:10:00+00:00" if long_state == "confirmed_structure" else None,
    )
    short_obs = StructureSideObservation("short", short_state, None, None, None)
    return MarketStructureResult("1.0.0", 2, 2, 0.0, 5, (), long_obs, short_obs, "sha256:structure")


def _liquidity(bullish_state: str = "confirmed_sweep", bearish_state: str = "insufficient_data") -> LiquiditySweepResult:
    bullish = LiquiditySweepObservation(
        "bullish", bullish_state, "sell_side",
        4100.0 if bullish_state == "confirmed_sweep" else None,
        2 if bullish_state == "confirmed_sweep" else 0,
        "2026-08-05T00:12:00+00:00" if bullish_state == "confirmed_sweep" else None,
        5.0 if bullish_state == "confirmed_sweep" else None,
        bullish_state == "confirmed_sweep",
    )
    bearish = LiquiditySweepObservation("bearish", bearish_state, "buy_side", None, 0, None, None, False)
    return LiquiditySweepResult("1.0.0", 10.0, 2, 1.0, 250, (), bullish, bearish, "sha256:liquidity")


def _bos_choch() -> BosChochResult:
    empty_bull = StructureBreakObservation("bullish", "no_break", None, None, None, None, None, None, None)
    empty_bear = StructureBreakObservation("bearish", "no_break", None, None, None, None, None, None, None)
    return BosChochResult("1.0.0", 1.0, 250, (), empty_bull, empty_bear, "sha256:bos_choch")


def _retest(bullish_state: str = "confirmed_retest", bearish_state: str = "insufficient_data") -> RetestResult:
    bullish = RetestObservation(
        "bullish", bullish_state,
        "BOS" if bullish_state == "confirmed_retest" else None,
        4100.0 if bullish_state == "confirmed_retest" else None,
        "2026-08-05T00:05:00+00:00" if bullish_state == "confirmed_retest" else None,
        "2026-08-05T00:08:00+00:00" if bullish_state == "confirmed_retest" else None,
        "2026-08-05T00:09:00+00:00" if bullish_state == "confirmed_retest" else None,
        3.0 if bullish_state == "confirmed_retest" else None,
    )
    bearish = RetestObservation("bearish", bearish_state, None, None, None, None, None, None)
    return RetestResult("1.0.0", 5.0, 0.0, 10.0, 100, (), bullish, bearish, "sha256:retest")


def _detect(**overrides):
    defaults = dict(
        market_structure=_structure(), liquidity_sweep=_liquidity(),
        bos_choch=_bos_choch(), retest=_retest(),
    )
    defaults.update(overrides)
    return detect_pattern_candidates(**defaults)


def _slot(result, hypothesis_id: str):
    return next(item for item in result.slots if item.hypothesis_id == hypothesis_id)


def test_confirmed_causal_observations_produce_draft_confirmed_candidates() -> None:
    result = _detect()
    assert len(result.slots) == 6
    for hypothesis_id in ("market_structure_long", "liquidity_sweep_reclaim_long", "structure_break_long"):
        slot = _slot(result, hypothesis_id)
        assert slot.condition_state == "candidate_confirmed"
        assert slot.lifecycle_state == "draft"
        assert slot.observed_at is not None
        assert slot.evidence
    for hypothesis_id in ("market_structure_short", "liquidity_sweep_reclaim_short", "structure_break_short"):
        slot = _slot(result, hypothesis_id)
        assert slot.condition_state == "insufficient_data"
        assert slot.observed_at is None
        assert slot.evidence == {}
    assert result.fingerprint.startswith("sha256:")
    assert "buy" not in result.fingerprint
    assert result.interpretation == "research_pattern_candidate_draft_not_trading_signal_not_order"


def test_no_candidate_is_distinguished_from_insufficient_data() -> None:
    result = _detect(
        market_structure=_structure(long_state="conflicting", short_state="partial"),
        liquidity_sweep=_liquidity(bullish_state="no_sweep", bearish_state="conflicting"),
        retest=_retest(bullish_state="no_retest", bearish_state="unconfirmed_retest"),
    )
    for hypothesis_id in (
        "market_structure_long", "market_structure_short",
        "liquidity_sweep_reclaim_long", "liquidity_sweep_reclaim_short",
        "structure_break_long", "structure_break_short",
    ):
        slot = _slot(result, hypothesis_id)
        assert slot.condition_state == "no_candidate"
        assert slot.observed_at is None
        assert slot.evidence


def test_result_is_deterministic_for_identical_input() -> None:
    first = _detect()
    second = _detect()
    assert first.fingerprint == second.fingerprint
    assert first.slots == second.slots
    for hypothesis_id in ("market_structure_long", "liquidity_sweep_reclaim_long", "structure_break_long"):
        assert _slot(first, hypothesis_id).candidate_id == _slot(second, hypothesis_id).candidate_id


def test_changed_upstream_fingerprint_changes_result_fingerprint() -> None:
    baseline = _detect()
    changed = _detect(liquidity_sweep=replace(_liquidity(), fingerprint="sha256:different"))
    assert baseline.fingerprint != changed.fingerprint


def test_rejects_empty_upstream_fingerprint() -> None:
    with pytest.raises(ValueError):
        _detect(market_structure=replace(_structure(), fingerprint=""))


def test_rejects_blank_upstream_fingerprint_on_any_input() -> None:
    with pytest.raises(ValueError):
        _detect(retest=replace(_retest(), fingerprint="   "))
