from dataclasses import asdict, dataclass

from backend.app.analysis.replay_analysis import create_replay_analysis_context
from backend.app.database.multiple_testing_repository import (
    count_family_trials,
    register_trial as register_multiple_testing_trial,
)
from backend.app.database.pattern_candidate_backtest_repository import (
    PersistedPatternCandidateBacktest,
    get_latest_pattern_candidate_backtest,
    store_pattern_candidate_backtest,
)
from backend.app.database.pattern_candidate_repository import (
    PatternCandidateOwnershipError,
    PersistedPatternCandidate,
    classify_pattern_candidate,
    get_latest_accepted_candidate_for_hypothesis,
    get_pattern_candidate,
    register_pattern_candidate,
)
from backend.app.database.replay_session_repository import (
    ReplaySession,
    get_replay_session,
)
from backend.app.strategies.pattern_candidate import detect_pattern_candidates
from backend.app.strategies.pattern_candidate_backtest import (
    ACCEPTED_FOR_SHADOW,
    REJECTED,
    bonferroni_corrected_scenario,
    classify_backtest_verdict,
    run_pattern_candidate_backtest,
)


REPLAY_PATTERN_CANDIDATES_API_VERSION = "1.0.0"


class PatternCandidateNotConfirmedError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReplayPatternCandidates:
    session_id: str
    symbol: str
    timeframe: str
    parameters: dict[str, object]
    lineage: dict[str, object]
    pattern_candidates: dict[str, object]
    interpretation: str = "research_pattern_candidate_draft_not_trading_signal_not_order"
    api_version: str = REPLAY_PATTERN_CANDIDATES_API_VERSION


def create_replay_pattern_candidates(
    *, session: ReplaySession, timeframe: str, bar_limit: int,
    pivot_left: int = 2, pivot_right: int = 2, equality_tolerance_bps: float = 0.0,
    liquidity_pool_tolerance_bps: float = 10.0, liquidity_minimum_touches: int = 2,
    liquidity_minimum_sweep_bps: float = 1.0, liquidity_maximum_pool_age_bars: int = 250,
    bos_choch_minimum_close_break_bps: float = 1.0, bos_choch_maximum_pivot_age_bars: int = 250,
    retest_touch_tolerance_bps: float = 5.0, retest_confirmation_close_bps: float = 0.0,
    retest_invalidation_close_bps: float = 10.0, retest_maximum_age_bars: int = 100,
) -> ReplayPatternCandidates:
    """Assemble draft pattern candidates from a completed replay session's causal detectors."""
    context = create_replay_analysis_context(
        session=session, timeframe=timeframe, ema_period=20, rsi_period=14, atr_period=14,
        bar_limit=bar_limit, pivot_left=pivot_left, pivot_right=pivot_right,
        equality_tolerance_bps=equality_tolerance_bps,
        liquidity_pool_tolerance_bps=liquidity_pool_tolerance_bps,
        liquidity_minimum_touches=liquidity_minimum_touches,
        liquidity_minimum_sweep_bps=liquidity_minimum_sweep_bps,
        liquidity_maximum_pool_age_bars=liquidity_maximum_pool_age_bars,
        bos_choch_minimum_close_break_bps=bos_choch_minimum_close_break_bps,
        bos_choch_maximum_pivot_age_bars=bos_choch_maximum_pivot_age_bars,
        retest_touch_tolerance_bps=retest_touch_tolerance_bps,
        retest_confirmation_close_bps=retest_confirmation_close_bps,
        retest_invalidation_close_bps=retest_invalidation_close_bps,
        retest_maximum_age_bars=retest_maximum_age_bars,
    )
    result = detect_pattern_candidates(
        market_structure=context.market_structure, liquidity_sweep=context.liquidity_sweep,
        bos_choch=context.bos_choch, retest=context.retest,
    )
    return ReplayPatternCandidates(
        session_id=session.session_id, symbol=session.symbol, timeframe=timeframe,
        parameters={
            "bar_limit": bar_limit, "pivot_left": pivot_left, "pivot_right": pivot_right,
            "equality_tolerance_bps": equality_tolerance_bps,
            "liquidity_pool_tolerance_bps": liquidity_pool_tolerance_bps,
            "liquidity_minimum_touches": liquidity_minimum_touches,
            "liquidity_minimum_sweep_bps": liquidity_minimum_sweep_bps,
            "liquidity_maximum_pool_age_bars": liquidity_maximum_pool_age_bars,
            "bos_choch_minimum_close_break_bps": bos_choch_minimum_close_break_bps,
            "bos_choch_maximum_pivot_age_bars": bos_choch_maximum_pivot_age_bars,
            "retest_touch_tolerance_bps": retest_touch_tolerance_bps,
            "retest_confirmation_close_bps": retest_confirmation_close_bps,
            "retest_invalidation_close_bps": retest_invalidation_close_bps,
            "retest_maximum_age_bars": retest_maximum_age_bars,
        },
        lineage=context.analysis.lineage,
        pattern_candidates=asdict(result),
    )


def register_replay_pattern_candidate(
    *, session: ReplaySession, hypothesis_id: str, actor: str, actor_role: str,
    timeframe: str, bar_limit: int,
    pivot_left: int = 2, pivot_right: int = 2, equality_tolerance_bps: float = 0.0,
    liquidity_pool_tolerance_bps: float = 10.0, liquidity_minimum_touches: int = 2,
    liquidity_minimum_sweep_bps: float = 1.0, liquidity_maximum_pool_age_bars: int = 250,
    bos_choch_minimum_close_break_bps: float = 1.0, bos_choch_maximum_pivot_age_bars: int = 250,
    retest_touch_tolerance_bps: float = 5.0, retest_confirmation_close_bps: float = 0.0,
    retest_invalidation_close_bps: float = 10.0, retest_maximum_age_bars: int = 100,
) -> PersistedPatternCandidate:
    """Recompute the current draft candidates and persist the requested confirmed slot.

    The client never supplies evidence or condition_state directly -- the server
    always recomputes from the completed replay session so a "registered" record
    can only ever reflect a causal detector result, never a client-asserted claim.
    """
    analysis = create_replay_pattern_candidates(
        session=session, timeframe=timeframe, bar_limit=bar_limit,
        pivot_left=pivot_left, pivot_right=pivot_right,
        equality_tolerance_bps=equality_tolerance_bps,
        liquidity_pool_tolerance_bps=liquidity_pool_tolerance_bps,
        liquidity_minimum_touches=liquidity_minimum_touches,
        liquidity_minimum_sweep_bps=liquidity_minimum_sweep_bps,
        liquidity_maximum_pool_age_bars=liquidity_maximum_pool_age_bars,
        bos_choch_minimum_close_break_bps=bos_choch_minimum_close_break_bps,
        bos_choch_maximum_pivot_age_bars=bos_choch_maximum_pivot_age_bars,
        retest_touch_tolerance_bps=retest_touch_tolerance_bps,
        retest_confirmation_close_bps=retest_confirmation_close_bps,
        retest_invalidation_close_bps=retest_invalidation_close_bps,
        retest_maximum_age_bars=retest_maximum_age_bars,
    )
    candidates = analysis.pattern_candidates
    slot = next(
        (item for item in candidates["slots"] if item["hypothesis_id"] == hypothesis_id),
        None,
    )
    if slot is None:
        raise ValueError("unknown hypothesis_id")
    if slot["condition_state"] != "candidate_confirmed":
        raise PatternCandidateNotConfirmedError(
            "hypothesis is not currently confirmed for this replay session and parameters"
        )
    return register_pattern_candidate(
        created_by=actor, actor_role=actor_role, replay_session_id=session.session_id,
        candidate_id=slot["candidate_id"], hypothesis_id=slot["hypothesis_id"],
        hypothesis_version=slot["hypothesis_version"], family=slot["family"],
        direction=slot["direction"], condition_state=slot["condition_state"],
        observed_at=slot["observed_at"], evidence=slot["evidence"],
        pattern_candidate_version=candidates["version"],
        hypothesis_registry_version=candidates["hypothesis_registry_version"],
        source_fingerprint=candidates["fingerprint"], timeframe=timeframe,
        parameters=analysis.parameters,
    )


def evaluate_replay_pattern_candidate_backtest(
    *, candidate_id: str, actor: str, actor_role: str, horizon_bars: int = 3,
    spread_bps: float = 2.0, commission_bps: float = 1.0, slippage_bps: float = 1.0,
    latency_bps: float = 0.5, adverse_multiplier: float = 1.5, stress_multiplier: float = 2.5,
) -> PersistedPatternCandidateBacktest:
    """Recompute a registered candidate's replay context and backtest it.

    The candidate's own stored timeframe/parameters are always used, so the
    backtest reflects exactly the causal detector configuration the
    candidate was registered under -- never client-supplied values.
    """
    candidate = get_pattern_candidate(candidate_id)
    if candidate.created_by != actor:
        raise PatternCandidateOwnershipError("pattern candidate belongs to another user")
    session = get_replay_session(candidate.replay_session_id)
    parameters = candidate.parameters
    context = create_replay_analysis_context(
        session=session, timeframe=candidate.timeframe, ema_period=20, rsi_period=14, atr_period=14,
        bar_limit=parameters["bar_limit"], pivot_left=parameters["pivot_left"],
        pivot_right=parameters["pivot_right"],
        equality_tolerance_bps=parameters["equality_tolerance_bps"],
        liquidity_pool_tolerance_bps=parameters["liquidity_pool_tolerance_bps"],
        liquidity_minimum_touches=parameters["liquidity_minimum_touches"],
        liquidity_minimum_sweep_bps=parameters["liquidity_minimum_sweep_bps"],
        liquidity_maximum_pool_age_bars=parameters["liquidity_maximum_pool_age_bars"],
        bos_choch_minimum_close_break_bps=parameters["bos_choch_minimum_close_break_bps"],
        bos_choch_maximum_pivot_age_bars=parameters["bos_choch_maximum_pivot_age_bars"],
        retest_touch_tolerance_bps=parameters["retest_touch_tolerance_bps"],
        retest_confirmation_close_bps=parameters["retest_confirmation_close_bps"],
        retest_invalidation_close_bps=parameters["retest_invalidation_close_bps"],
        retest_maximum_age_bars=parameters["retest_maximum_age_bars"],
    )
    backtest = run_pattern_candidate_backtest(
        candidate_id=candidate.candidate_id, hypothesis_id=candidate.hypothesis_id,
        bars=context.bars.bars, retest=context.retest, liquidity_sweep=context.liquidity_sweep,
        market_structure=context.market_structure, rsi=context.indicators.rsi,
        horizon_bars=horizon_bars, spread_bps=spread_bps, commission_bps=commission_bps,
        slippage_bps=slippage_bps, latency_bps=latency_bps,
        adverse_multiplier=adverse_multiplier, stress_multiplier=stress_multiplier,
    )
    cost_parameters = {
        "spread_bps": spread_bps, "commission_bps": commission_bps,
        "slippage_bps": slippage_bps, "latency_bps": latency_bps,
        "adverse_multiplier": adverse_multiplier, "stress_multiplier": stress_multiplier,
    }
    persisted = store_pattern_candidate_backtest(
        candidate_id=candidate.candidate_id, actor=actor, actor_role=actor_role,
        horizon_bars=horizon_bars, cost_parameters=cost_parameters,
        result=asdict(backtest), fingerprint=backtest.fingerprint,
    )
    # Registered unconditionally, whether or not this candidate is ever
    # classified: the multiple-testing budget must count every hypothesis
    # variant tried against this dataset (Phase 3/4 contract), not just the
    # ones a user later chooses to accept.
    register_multiple_testing_trial(
        family_key=candidate.replay_session_id, candidate_id=candidate.candidate_id,
        backtest_id=persisted.backtest_id, hypothesis_id=candidate.hypothesis_id, actor=actor,
    )
    return persisted


@dataclass(frozen=True)
class PatternCandidateClassificationOutcome:
    candidate: PersistedPatternCandidate
    family_trial_count: int
    corrected_scenario: dict[str, object]
    previous_accepted_candidate_comparison: dict[str, object] | None


def classify_replay_pattern_candidate(
    *, candidate_id: str, actor: str, actor_role: str, expected_state_version: int,
) -> PatternCandidateClassificationOutcome:
    """Move an "evaluated" candidate to accepted_for_shadow/rejected/insufficient_evidence.

    The verdict comes from the candidate's latest backtest "normal" cost
    scenario, after a Bonferroni family-wise error correction across every
    backtest trial registered against the same replay session (the
    multiple-testing registry). If that verdict would be accepted_for_shadow
    and a previously accepted_for_shadow candidate already exists for the
    same hypothesis (any replay session), the new candidate must also beat
    that candidate's net return -- the "previously accepted candidate"
    baseline -- or it is rejected instead. All deterministic, no client
    input. accepted_for_shadow records that all of this evidence held; it
    does not authorize real trading (Phase 9 SHADOW does not exist yet) or
    any order.
    """
    candidate = get_pattern_candidate(candidate_id)
    if candidate.created_by != actor:
        raise PatternCandidateOwnershipError("pattern candidate belongs to another user")
    backtest = get_latest_pattern_candidate_backtest(candidate_id)
    normal_scenario = next(
        item for item in backtest.result["scenarios"] if item["scenario"] == "normal"
    )
    family_trial_count = count_family_trials(candidate.replay_session_id)
    corrected_scenario = bonferroni_corrected_scenario(
        normal_scenario, family_trial_count=family_trial_count,
    )
    next_state = classify_backtest_verdict(
        status=corrected_scenario["status"], reason=corrected_scenario["reason"],
    )

    previous_comparison: dict[str, object] | None = None
    if next_state == ACCEPTED_FOR_SHADOW:
        previous = get_latest_accepted_candidate_for_hypothesis(
            hypothesis_id=candidate.hypothesis_id, exclude_candidate_id=candidate_id,
        )
        if previous is not None:
            previous_backtest = get_latest_pattern_candidate_backtest(previous.candidate_id)
            previous_normal = next(
                item for item in previous_backtest.result["scenarios"] if item["scenario"] == "normal"
            )
            previous_mean = previous_normal["net_mean_return_percent"]
            current_mean = corrected_scenario["net_mean_return_percent"]
            beats_previous = (
                current_mean > previous_mean if previous_mean is not None and current_mean is not None else None
            )
            previous_comparison = {
                "previous_candidate_id": previous.candidate_id,
                "previous_net_mean_return_percent": previous_mean,
                "current_net_mean_return_percent": current_mean,
                "beats_previous_accepted_candidate": beats_previous,
            }
            if beats_previous is False:
                next_state = REJECTED

    classified = classify_pattern_candidate(
        candidate_id=candidate_id, actor=actor, actor_role=actor_role,
        expected_state_version=expected_state_version, next_lifecycle_state=next_state,
    )
    return PatternCandidateClassificationOutcome(
        candidate=classified, family_trial_count=family_trial_count,
        corrected_scenario=corrected_scenario,
        previous_accepted_candidate_comparison=previous_comparison,
    )
