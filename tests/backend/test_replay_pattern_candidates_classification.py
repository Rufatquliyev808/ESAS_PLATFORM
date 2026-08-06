from pathlib import Path

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.multiple_testing_repository import register_trial
from backend.app.database.pattern_candidate_backtest_repository import store_pattern_candidate_backtest
from backend.app.database.pattern_candidate_repository import get_pattern_candidate, register_pattern_candidate
from backend.app.strategies.replay_pattern_candidates import classify_replay_pattern_candidate


def _prepare(database_path: Path, session_id: str = "rps_test", created_by: str = "TEST-USER") -> None:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO replay_sessions
            (
                session_id, created_by, symbol, start_at, end_at, mode, state,
                replay_contract_version, quality_rule_version, dataset_tick_count,
                dataset_fingerprint, processed_ticks, created_at, updated_at, completed_at
            ) VALUES (?, ?, 'GOLD', '2026-08-05T00:00:00+00:00', '2026-08-05T01:00:00+00:00',
                      'max_speed', 'completed', '1.0', '1.0', 10, 'sha256:dataset', 10,
                      '2026-08-05T00:00:00+00:00', '2026-08-05T00:00:00+00:00', '2026-08-05T00:00:00+00:00');
            """,
            (session_id, created_by),
        )


def _register(candidate_id: str, hypothesis_id: str = "structure_break_long", session_id: str = "rps_test", created_by: str = "TEST-USER"):
    family = "market_structure" if hypothesis_id.startswith("market_structure") else "bos_choch_retest"
    return register_pattern_candidate(
        created_by=created_by, actor_role="operator", replay_session_id=session_id,
        candidate_id=candidate_id, hypothesis_id=hypothesis_id,
        hypothesis_version="1.0.0", family=family, direction="long",
        condition_state="candidate_confirmed", observed_at="2026-08-05T00:10:00+00:00",
        evidence={}, pattern_candidate_version="1.0.0", hypothesis_registry_version="1.0.0",
        source_fingerprint="sha256:pattern", timeframe="M5", parameters={"bar_limit": 500},
    )


def _supportive_scenario(net_mean: float) -> dict[str, object]:
    return {
        "scenario": "normal", "total_cost_bps": 4.5, "effective_sample_size": 40,
        "net_mean_return_percent": net_mean, "hit_rate_percent": 60.0,
        "standardized_effect_size": 1.0, "sample_standard_deviation": 3.0,
        "confidence_interval_low_percent": net_mean - 0.5, "confidence_interval_high_percent": net_mean + 0.5,
        "status": "supportive_evidence", "reason": "ci_entirely_above_zero_baseline",
        "random_timing_baseline_sample_size": 0, "random_timing_baseline_mean_return_percent": None,
        "beats_random_timing_baseline": None,
        "single_feature_baseline_sample_size": 0, "single_feature_baseline_mean_return_percent": None,
        "beats_single_feature_baseline": None,
    }


def _store_backtest(
    candidate_id: str, net_mean: float, hypothesis_id: str = "structure_break_long",
    session_id: str = "rps_test", created_by: str = "TEST-USER",
):
    persisted = store_pattern_candidate_backtest(
        candidate_id=candidate_id, actor=created_by, actor_role="operator",
        horizon_bars=3, cost_parameters={}, result={"scenarios": [_supportive_scenario(net_mean)]},
        fingerprint=f"sha256:{candidate_id}",
    )
    register_trial(
        family_key=session_id, candidate_id=candidate_id, backtest_id=persisted.backtest_id,
        hypothesis_id=hypothesis_id, actor=created_by,
    )
    return persisted


def _classify(candidate_id: str, created_by: str = "TEST-USER"):
    current = get_pattern_candidate(candidate_id)
    return classify_replay_pattern_candidate(
        candidate_id=candidate_id, actor=created_by, actor_role="operator",
        expected_state_version=current.state_version,
    )


def _store_backtest_with_overlap(
    candidate_id: str, *, raw_event_count: int, discarded_for_overlap: int,
    scenario: dict[str, object], hypothesis_id: str = "structure_break_long",
    session_id: str = "rps_test", created_by: str = "TEST-USER",
):
    persisted = store_pattern_candidate_backtest(
        candidate_id=candidate_id, actor=created_by, actor_role="operator",
        horizon_bars=3, cost_parameters={},
        result={
            "raw_event_count": raw_event_count, "discarded_for_overlap": discarded_for_overlap,
            "scenarios": [scenario],
        },
        fingerprint=f"sha256:{candidate_id}",
    )
    register_trial(
        family_key=session_id, candidate_id=candidate_id, backtest_id=persisted.backtest_id,
        hypothesis_id=hypothesis_id, actor=created_by,
    )
    return persisted


def test_candidate_invalidated_for_leakage_when_purge_collapses_ample_raw_signal(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register("structure_break_long:leak")
    scenario = _supportive_scenario(2.0)
    scenario["effective_sample_size"] = 20  # below the reliability floor after purge
    _store_backtest_with_overlap(
        candidate.candidate_id, raw_event_count=40, discarded_for_overlap=15, scenario=scenario,
    )
    outcome = _classify(candidate.candidate_id)
    assert outcome.candidate.lifecycle_state == "invalid_leakage"


def test_candidate_stays_insufficient_evidence_when_raw_signal_was_never_ample(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register("structure_break_long:sparse")
    scenario = {
        "scenario": "normal", "total_cost_bps": 4.5, "effective_sample_size": 15,
        "net_mean_return_percent": 2.0, "hit_rate_percent": 60.0,
        "standardized_effect_size": None, "sample_standard_deviation": None,
        "confidence_interval_low_percent": None, "confidence_interval_high_percent": None,
        "status": "insufficient_evidence", "reason": "effective_sample_below_30",
        "random_timing_baseline_sample_size": 0, "random_timing_baseline_mean_return_percent": None,
        "beats_random_timing_baseline": None,
        "single_feature_baseline_sample_size": 0, "single_feature_baseline_mean_return_percent": None,
        "beats_single_feature_baseline": None,
    }
    # Raw signal itself was below the reliability floor (20 < 30) -- purging
    # a handful of overlaps on top of that is beside the point; this is
    # ordinary insufficient_evidence, not leakage-inflated evidence.
    _store_backtest_with_overlap(
        candidate.candidate_id, raw_event_count=20, discarded_for_overlap=5, scenario=scenario,
    )
    outcome = _classify(candidate.candidate_id)
    assert outcome.candidate.lifecycle_state == "insufficient_evidence"


def test_candidate_not_invalidated_when_nothing_was_purged(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register("structure_break_long:clean")
    scenario = _supportive_scenario(2.0)
    _store_backtest_with_overlap(
        candidate.candidate_id, raw_event_count=40, discarded_for_overlap=0, scenario=scenario,
    )
    outcome = _classify(candidate.candidate_id)
    assert outcome.candidate.lifecycle_state == "accepted_for_shadow"


def test_first_ever_accepted_candidate_has_no_previous_comparison(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register("structure_break_long:a")
    _store_backtest(candidate.candidate_id, net_mean=2.0)
    outcome = _classify(candidate.candidate_id)
    assert outcome.candidate.lifecycle_state == "accepted_for_shadow"
    assert outcome.previous_accepted_candidate_comparison is None


def test_candidate_rejected_when_it_underperforms_previous_accepted_candidate(isolated_database: Path) -> None:
    # Distinct sessions (multiple-testing family keys) for each candidate, so
    # the Bonferroni correction stays at family_trial_count=1 for both and
    # this test isolates the previous-accepted-candidate gate specifically.
    _prepare(isolated_database, session_id="rps_first")
    _prepare(isolated_database, session_id="rps_second")
    first = _register("structure_break_long:first", session_id="rps_first")
    _store_backtest(first.candidate_id, net_mean=3.0, session_id="rps_first")
    first_outcome = _classify(first.candidate_id)
    assert first_outcome.candidate.lifecycle_state == "accepted_for_shadow"

    second = _register("structure_break_long:second", session_id="rps_second")
    _store_backtest(second.candidate_id, net_mean=1.0, session_id="rps_second")
    second_outcome = _classify(second.candidate_id)
    assert second_outcome.candidate.lifecycle_state == "rejected"
    comparison = second_outcome.previous_accepted_candidate_comparison
    assert comparison is not None
    assert comparison["previous_candidate_id"] == first.candidate_id
    assert comparison["previous_net_mean_return_percent"] == 3.0
    assert comparison["current_net_mean_return_percent"] == 1.0
    assert comparison["beats_previous_accepted_candidate"] is False


def test_candidate_accepted_when_it_beats_previous_accepted_candidate(isolated_database: Path) -> None:
    _prepare(isolated_database, session_id="rps_first")
    _prepare(isolated_database, session_id="rps_second")
    first = _register("structure_break_long:first", session_id="rps_first")
    _store_backtest(first.candidate_id, net_mean=1.0, session_id="rps_first")
    _classify(first.candidate_id)

    second = _register("structure_break_long:second", session_id="rps_second")
    _store_backtest(second.candidate_id, net_mean=3.0, session_id="rps_second")
    second_outcome = _classify(second.candidate_id)
    assert second_outcome.candidate.lifecycle_state == "accepted_for_shadow"
    assert second_outcome.previous_accepted_candidate_comparison["beats_previous_accepted_candidate"] is True


def test_previous_candidate_comparison_ignores_a_different_hypothesis(isolated_database: Path) -> None:
    _prepare(isolated_database, session_id="rps_other")
    _prepare(isolated_database, session_id="rps_solo")
    other = _register("market_structure_long:other", hypothesis_id="market_structure_long", session_id="rps_other")
    _store_backtest(other.candidate_id, net_mean=100.0, hypothesis_id="market_structure_long", session_id="rps_other")
    _classify(other.candidate_id)

    candidate = _register("structure_break_long:solo", session_id="rps_solo")
    _store_backtest(candidate.candidate_id, net_mean=2.0, session_id="rps_solo")
    outcome = _classify(candidate.candidate_id)
    assert outcome.candidate.lifecycle_state == "accepted_for_shadow"
    assert outcome.previous_accepted_candidate_comparison is None
