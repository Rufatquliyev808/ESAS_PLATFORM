from pathlib import Path
import sqlite3

import pytest

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.multiple_testing_repository import (
    count_family_trials,
    list_family_trials,
    register_trial,
)
from backend.app.database.pattern_candidate_backtest_repository import store_pattern_candidate_backtest
from backend.app.database.pattern_candidate_repository import register_pattern_candidate


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


def _register(session_id: str = "rps_test", created_by: str = "TEST-USER", candidate_id: str = "structure_break_long:abc"):
    return register_pattern_candidate(
        created_by=created_by, actor_role="operator", replay_session_id=session_id,
        candidate_id=candidate_id, hypothesis_id="structure_break_long",
        hypothesis_version="1.0.0", family="bos_choch_retest", direction="long",
        condition_state="candidate_confirmed", observed_at="2026-08-05T00:10:00+00:00",
        evidence={}, pattern_candidate_version="1.0.0", hypothesis_registry_version="1.0.0",
        source_fingerprint="sha256:pattern", timeframe="M5", parameters={"bar_limit": 500},
    )


def _backtest(candidate_id: str, created_by: str = "TEST-USER"):
    return store_pattern_candidate_backtest(
        candidate_id=candidate_id, actor=created_by, actor_role="operator",
        horizon_bars=3, cost_parameters={"spread_bps": 2.0}, result={"trades": []},
        fingerprint=f"sha256:backtest:{candidate_id}",
    )


def test_register_trial_assigns_increasing_family_sequence(isolated_database: Path) -> None:
    _prepare(isolated_database)
    first_candidate = _register(candidate_id="c1")
    second_candidate = _register(candidate_id="c2")
    first_backtest = _backtest(first_candidate.candidate_id)
    second_backtest = _backtest(second_candidate.candidate_id)

    first_trial = register_trial(
        family_key="rps_test", candidate_id=first_candidate.candidate_id,
        backtest_id=first_backtest.backtest_id, hypothesis_id="structure_break_long", actor="TEST-USER",
    )
    second_trial = register_trial(
        family_key="rps_test", candidate_id=second_candidate.candidate_id,
        backtest_id=second_backtest.backtest_id, hypothesis_id="structure_break_long", actor="TEST-USER",
    )
    assert first_trial.family_sequence == 1
    assert second_trial.family_sequence == 2
    assert count_family_trials("rps_test") == 2


def test_register_trial_is_idempotent_by_backtest_id(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    backtest = _backtest(candidate.candidate_id)
    first = register_trial(
        family_key="rps_test", candidate_id=candidate.candidate_id,
        backtest_id=backtest.backtest_id, hypothesis_id="structure_break_long", actor="TEST-USER",
    )
    second = register_trial(
        family_key="rps_test", candidate_id=candidate.candidate_id,
        backtest_id=backtest.backtest_id, hypothesis_id="structure_break_long", actor="TEST-USER",
    )
    assert first == second
    assert count_family_trials("rps_test") == 1


def test_families_are_isolated_by_family_key(isolated_database: Path) -> None:
    _prepare(isolated_database, session_id="rps_a")
    _prepare(isolated_database, session_id="rps_b")
    candidate_a = _register(session_id="rps_a", candidate_id="c-a")
    candidate_b = _register(session_id="rps_b", candidate_id="c-b")
    backtest_a = _backtest(candidate_a.candidate_id)
    backtest_b = _backtest(candidate_b.candidate_id)

    register_trial(
        family_key="rps_a", candidate_id=candidate_a.candidate_id,
        backtest_id=backtest_a.backtest_id, hypothesis_id="structure_break_long", actor="TEST-USER",
    )
    register_trial(
        family_key="rps_b", candidate_id=candidate_b.candidate_id,
        backtest_id=backtest_b.backtest_id, hypothesis_id="structure_break_long", actor="TEST-USER",
    )
    assert count_family_trials("rps_a") == 1
    assert count_family_trials("rps_b") == 1


def test_count_family_trials_is_zero_for_unknown_family(isolated_database: Path) -> None:
    _prepare(isolated_database)
    assert count_family_trials("no-such-family") == 0


def test_list_family_trials_is_ordered_by_sequence(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidates = [_register(candidate_id=f"c{i}") for i in range(3)]
    backtests = [_backtest(candidate.candidate_id) for candidate in candidates]
    for candidate, backtest in zip(candidates, backtests):
        register_trial(
            family_key="rps_test", candidate_id=candidate.candidate_id,
            backtest_id=backtest.backtest_id, hypothesis_id="structure_break_long", actor="TEST-USER",
        )
    trials = list_family_trials("rps_test")
    assert [trial.family_sequence for trial in trials] == [1, 2, 3]
    assert [trial.candidate_id for trial in trials] == [c.candidate_id for c in candidates]


def test_multiple_testing_trials_are_append_only(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    backtest = _backtest(candidate.candidate_id)
    trial = register_trial(
        family_key="rps_test", candidate_id=candidate.candidate_id,
        backtest_id=backtest.backtest_id, hypothesis_id="structure_break_long", actor="TEST-USER",
    )
    with get_connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE multiple_testing_trials SET actor = 'someone-else' WHERE trial_id = ?;",
                (trial.trial_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM multiple_testing_trials WHERE trial_id = ?;",
                (trial.trial_id,),
            )
