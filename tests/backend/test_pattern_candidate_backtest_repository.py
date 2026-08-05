from pathlib import Path

import pytest

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.pattern_candidate_backtest_repository import (
    PatternCandidateBacktestNotFoundError,
    get_latest_pattern_candidate_backtest,
    store_pattern_candidate_backtest,
)
from backend.app.database.pattern_candidate_repository import (
    PatternCandidateConflictError,
    PatternCandidateOwnershipError,
    archive_pattern_candidate,
    register_pattern_candidate,
)


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


def _register(session_id: str = "rps_test", created_by: str = "TEST-USER"):
    return register_pattern_candidate(
        created_by=created_by, actor_role="operator", replay_session_id=session_id,
        candidate_id="structure_break_long:abc", hypothesis_id="structure_break_long",
        hypothesis_version="1.0.0", family="bos_choch_retest", direction="bullish",
        condition_state="candidate_confirmed", observed_at="2026-08-05T00:10:00+00:00",
        evidence={}, pattern_candidate_version="1.0.0", hypothesis_registry_version="1.0.0",
        source_fingerprint="sha256:pattern", timeframe="M5", parameters={"bar_limit": 500},
    )


def _store(candidate_id: str, created_by: str = "TEST-USER"):
    return store_pattern_candidate_backtest(
        candidate_id=candidate_id, actor=created_by, actor_role="operator",
        horizon_bars=3, cost_parameters={"spread_bps": 2.0}, result={"trades": []},
        fingerprint="sha256:backtest",
    )


def test_store_transitions_registered_to_evaluated_with_audit(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    backtest = _store(candidate.candidate_id)
    assert backtest.horizon_bars == 3
    assert backtest.result == {"trades": []}
    with get_connection() as connection:
        row = connection.execute(
            "SELECT lifecycle_state, state_version FROM pattern_candidates WHERE candidate_id = ?;",
            (candidate.candidate_id,),
        ).fetchone()
        audit = connection.execute(
            "SELECT action, previous_state, next_state FROM pattern_candidate_audit WHERE candidate_id = ? ORDER BY audit_id;",
            (candidate.candidate_id,),
        ).fetchall()
    assert row["lifecycle_state"] == "evaluated"
    assert row["state_version"] == candidate.state_version + 1
    assert [tuple(item) for item in audit] == [
        ("register", None, "registered"),
        ("evaluate", "registered", "evaluated"),
    ]


def test_re_running_backtest_stays_evaluated_and_appends_new_row(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    first = _store(candidate.candidate_id)
    second = _store(candidate.candidate_id)
    assert first.backtest_id != second.backtest_id
    with get_connection() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM pattern_candidate_backtests WHERE candidate_id = ?;",
            (candidate.candidate_id,),
        ).fetchone()[0]
        row = connection.execute(
            "SELECT lifecycle_state FROM pattern_candidates WHERE candidate_id = ?;",
            (candidate.candidate_id,),
        ).fetchone()
    assert count == 2
    assert row["lifecycle_state"] == "evaluated"
    latest = get_latest_pattern_candidate_backtest(candidate.candidate_id)
    assert latest.backtest_id == second.backtest_id


def test_archived_candidate_cannot_be_backtested(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    archive_pattern_candidate(
        candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=candidate.state_version,
    )
    with pytest.raises(PatternCandidateConflictError):
        _store(candidate.candidate_id)


def test_backtest_enforces_ownership(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    with pytest.raises(PatternCandidateOwnershipError):
        _store(candidate.candidate_id, created_by="OTHER-USER")


def test_missing_backtest_raises_not_found(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    with pytest.raises(PatternCandidateBacktestNotFoundError):
        get_latest_pattern_candidate_backtest(candidate.candidate_id)
