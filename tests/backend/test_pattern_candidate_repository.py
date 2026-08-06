from pathlib import Path

import pytest

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.pattern_candidate_backtest_repository import store_pattern_candidate_backtest
from backend.app.database.pattern_candidate_repository import (
    PatternCandidateConflictError,
    PatternCandidateListPosition,
    PatternCandidateNotFoundError,
    PatternCandidateOwnershipError,
    archive_pattern_candidate,
    block_pattern_candidate_for_data_quality,
    classify_pattern_candidate,
    get_latest_accepted_candidate_for_hypothesis,
    get_pattern_candidate,
    list_pattern_candidates,
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


def _register(session_id: str = "rps_test", created_by: str = "TEST-USER", candidate_id: str = "market_structure_long:abc"):
    return register_pattern_candidate(
        created_by=created_by, actor_role="operator", replay_session_id=session_id,
        candidate_id=candidate_id, hypothesis_id="market_structure_long",
        hypothesis_version="1.0.0", family="market_structure", direction="long",
        condition_state="candidate_confirmed", observed_at="2026-08-05T00:10:00+00:00",
        evidence={"latest_high": "HH", "latest_low": "HL"},
        pattern_candidate_version="1.0.0", hypothesis_registry_version="1.0.0",
        source_fingerprint="sha256:pattern", timeframe="M5",
        parameters={"bar_limit": 500},
    )


def _accept(candidate_id: str, created_by: str = "TEST-USER"):
    store_pattern_candidate_backtest(
        candidate_id=candidate_id, actor=created_by, actor_role="operator",
        horizon_bars=3, cost_parameters={}, result={}, fingerprint=f"sha256:{candidate_id}",
    )
    candidate = get_pattern_candidate(candidate_id)
    return classify_pattern_candidate(
        candidate_id=candidate_id, actor=created_by, actor_role="operator",
        expected_state_version=candidate.state_version, next_lifecycle_state="accepted_for_shadow",
    )


def test_get_latest_accepted_candidate_for_hypothesis_returns_none_when_none_exist(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    assert get_latest_accepted_candidate_for_hypothesis(
        hypothesis_id=candidate.hypothesis_id, exclude_candidate_id=candidate.candidate_id,
    ) is None


def test_get_latest_accepted_candidate_for_hypothesis_finds_previous_accepted(isolated_database: Path) -> None:
    _prepare(isolated_database)
    first = _register(candidate_id="market_structure_long:first")
    _accept(first.candidate_id)
    second = _register(candidate_id="market_structure_long:second")
    found = get_latest_accepted_candidate_for_hypothesis(
        hypothesis_id="market_structure_long", exclude_candidate_id=second.candidate_id,
    )
    assert found is not None
    assert found.candidate_id == first.candidate_id


def test_get_latest_accepted_candidate_for_hypothesis_excludes_self(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    _accept(candidate.candidate_id)
    found = get_latest_accepted_candidate_for_hypothesis(
        hypothesis_id=candidate.hypothesis_id, exclude_candidate_id=candidate.candidate_id,
    )
    assert found is None


def test_get_latest_accepted_candidate_for_hypothesis_ignores_other_hypotheses(isolated_database: Path) -> None:
    _prepare(isolated_database)
    accepted = _register(candidate_id="market_structure_long:acc")
    _accept(accepted.candidate_id)
    other = register_pattern_candidate(
        created_by="TEST-USER", actor_role="operator", replay_session_id="rps_test",
        candidate_id="structure_break_long:other", hypothesis_id="structure_break_long",
        hypothesis_version="1.0.0", family="bos_choch_retest", direction="long",
        condition_state="candidate_confirmed", observed_at="2026-08-05T00:10:00+00:00",
        evidence={}, pattern_candidate_version="1.0.0", hypothesis_registry_version="1.0.0",
        source_fingerprint="sha256:pattern", timeframe="M5", parameters={"bar_limit": 500},
    )
    found = get_latest_accepted_candidate_for_hypothesis(
        hypothesis_id="structure_break_long", exclude_candidate_id=other.candidate_id,
    )
    assert found is None


def test_register_persists_confirmed_candidate_with_initial_audit(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    assert candidate.lifecycle_state == "registered"
    assert candidate.state_version == 0
    assert candidate.evidence == {"latest_high": "HH", "latest_low": "HL"}
    with get_connection() as connection:
        audit = connection.execute(
            "SELECT action, previous_state, next_state FROM pattern_candidate_audit WHERE candidate_id = ?;",
            (candidate.candidate_id,),
        ).fetchall()
    assert [tuple(row) for row in audit] == [("register", None, "registered")]


def test_register_rejects_unconfirmed_condition_state(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with pytest.raises(ValueError):
        register_pattern_candidate(
            created_by="TEST-USER", actor_role="operator", replay_session_id="rps_test",
            candidate_id="x", hypothesis_id="market_structure_long", hypothesis_version="1.0.0",
            family="market_structure", direction="long", condition_state="no_candidate",
            observed_at=None, evidence={}, pattern_candidate_version="1.0.0",
            hypothesis_registry_version="1.0.0", source_fingerprint="sha256:pattern",
            timeframe="M5", parameters={},
        )


def test_register_is_idempotent_for_same_owner_and_conflicts_for_another(isolated_database: Path) -> None:
    _prepare(isolated_database)
    first = _register()
    second = _register()
    assert first == second
    with get_connection() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM pattern_candidates WHERE candidate_id = ?;",
            (first.candidate_id,),
        ).fetchone()[0]
    assert count == 1
    with pytest.raises(PatternCandidateOwnershipError):
        _register(created_by="OTHER-USER")


def test_get_and_list_are_owner_scoped(isolated_database: Path) -> None:
    _prepare(isolated_database, session_id="rps_a", created_by="USER-A")
    _prepare(isolated_database, session_id="rps_b", created_by="USER-B")
    a = _register(session_id="rps_a", created_by="USER-A", candidate_id="market_structure_long:a")
    _register(session_id="rps_b", created_by="USER-B", candidate_id="market_structure_long:b")

    assert get_pattern_candidate(a.candidate_id) == a
    with pytest.raises(PatternCandidateNotFoundError):
        get_pattern_candidate("missing")

    page_a = list_pattern_candidates(owner="USER-A")
    assert [item.candidate_id for item in page_a.items] == [a.candidate_id]
    page_b = list_pattern_candidates(owner="USER-B")
    assert len(page_b.items) == 1
    assert page_b.items[0].created_by == "USER-B"


def test_list_pagination_is_deterministic_and_gap_free(isolated_database: Path) -> None:
    _prepare(isolated_database)
    created = [
        _register(candidate_id=f"market_structure_long:{index}")
        for index in range(3)
    ]
    first_page = list_pattern_candidates(owner="TEST-USER", page_size=2)
    assert len(first_page.items) == 2
    assert first_page.next_position is not None
    second_page = list_pattern_candidates(
        owner="TEST-USER", page_size=2,
        after=PatternCandidateListPosition(
            first_page.next_position.created_at, first_page.next_position.candidate_id,
        ),
    )
    all_ids = {item.candidate_id for item in first_page.items} | {item.candidate_id for item in second_page.items}
    assert all_ids == {item.candidate_id for item in created}
    assert second_page.next_position is None


def test_archive_transitions_state_and_rejects_conflicts(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    archived = archive_pattern_candidate(
        candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=candidate.state_version,
    )
    assert archived.lifecycle_state == "archived"
    assert archived.state_version == candidate.state_version + 1

    with pytest.raises(PatternCandidateConflictError):
        archive_pattern_candidate(
            candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator",
            expected_state_version=candidate.state_version,
        )
    with pytest.raises(PatternCandidateNotFoundError):
        archive_pattern_candidate(
            candidate_id="missing", actor="TEST-USER", actor_role="operator",
            expected_state_version=0,
        )


def test_archive_enforces_ownership(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    with pytest.raises(PatternCandidateOwnershipError):
        archive_pattern_candidate(
            candidate_id=candidate.candidate_id, actor="OTHER-USER", actor_role="operator",
            expected_state_version=candidate.state_version,
        )


def test_archive_is_allowed_from_evaluated_state(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    with get_connection() as connection:
        connection.execute(
            "UPDATE pattern_candidates SET lifecycle_state = 'evaluated', state_version = state_version + 1 WHERE candidate_id = ?;",
            (candidate.candidate_id,),
        )
    evaluated = get_pattern_candidate(candidate.candidate_id)
    archived = archive_pattern_candidate(
        candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=evaluated.state_version,
    )
    assert archived.lifecycle_state == "archived"
    with get_connection() as connection:
        audit = connection.execute(
            "SELECT previous_state, next_state FROM pattern_candidate_audit WHERE candidate_id = ? ORDER BY audit_id;",
            (candidate.candidate_id,),
        ).fetchall()
    assert tuple(audit[-1]) == ("evaluated", "archived")


def _mark_evaluated(candidate_id: str) -> None:
    with get_connection() as connection:
        connection.execute(
            "UPDATE pattern_candidates SET lifecycle_state = 'evaluated', state_version = state_version + 1 WHERE candidate_id = ?;",
            (candidate_id,),
        )


def test_classify_transitions_evaluated_candidate_to_a_valid_outcome(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    _mark_evaluated(candidate.candidate_id)
    evaluated = get_pattern_candidate(candidate.candidate_id)
    classified = classify_pattern_candidate(
        candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=evaluated.state_version, next_lifecycle_state="accepted_for_shadow",
    )
    assert classified.lifecycle_state == "accepted_for_shadow"
    assert classified.state_version == evaluated.state_version + 1
    with get_connection() as connection:
        audit = connection.execute(
            "SELECT action, previous_state, next_state FROM pattern_candidate_audit WHERE candidate_id = ? ORDER BY audit_id;",
            (candidate.candidate_id,),
        ).fetchall()
    assert [tuple(row) for row in audit][-1] == ("classify", "evaluated", "accepted_for_shadow")


def test_classify_rejects_invalid_outcome_and_wrong_source_state(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    with pytest.raises(ValueError):
        classify_pattern_candidate(
            candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator",
            expected_state_version=candidate.state_version, next_lifecycle_state="archived",
        )
    with pytest.raises(PatternCandidateConflictError):
        classify_pattern_candidate(
            candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator",
            expected_state_version=candidate.state_version, next_lifecycle_state="rejected",
        )


def test_classify_enforces_ownership_and_optimistic_lock(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    _mark_evaluated(candidate.candidate_id)
    evaluated = get_pattern_candidate(candidate.candidate_id)
    with pytest.raises(PatternCandidateOwnershipError):
        classify_pattern_candidate(
            candidate_id=candidate.candidate_id, actor="OTHER-USER", actor_role="operator",
            expected_state_version=evaluated.state_version, next_lifecycle_state="rejected",
        )
    with pytest.raises(PatternCandidateConflictError):
        classify_pattern_candidate(
            candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator",
            expected_state_version=evaluated.state_version + 1, next_lifecycle_state="rejected",
        )


def test_block_for_data_quality_transitions_registered_candidate(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    blocked = block_pattern_candidate_for_data_quality(
        candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=candidate.state_version,
    )
    assert blocked.lifecycle_state == "blocked_by_data_quality"
    assert blocked.state_version == candidate.state_version + 1
    with get_connection() as connection:
        audit = connection.execute(
            "SELECT action, previous_state, next_state FROM pattern_candidate_audit WHERE candidate_id = ? ORDER BY audit_id;",
            (candidate.candidate_id,),
        ).fetchall()
    assert tuple(audit[-1]) == ("block_data_quality", "registered", "blocked_by_data_quality")


def test_block_for_data_quality_rejects_non_registered_state(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    _mark_evaluated(candidate.candidate_id)
    evaluated = get_pattern_candidate(candidate.candidate_id)
    with pytest.raises(PatternCandidateConflictError):
        block_pattern_candidate_for_data_quality(
            candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator",
            expected_state_version=evaluated.state_version,
        )


def test_block_for_data_quality_enforces_ownership_and_optimistic_lock(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    with pytest.raises(PatternCandidateOwnershipError):
        block_pattern_candidate_for_data_quality(
            candidate_id=candidate.candidate_id, actor="OTHER-USER", actor_role="operator",
            expected_state_version=candidate.state_version,
        )
    with pytest.raises(PatternCandidateConflictError):
        block_pattern_candidate_for_data_quality(
            candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator",
            expected_state_version=candidate.state_version + 1,
        )
    with pytest.raises(PatternCandidateNotFoundError):
        block_pattern_candidate_for_data_quality(
            candidate_id="missing", actor="TEST-USER", actor_role="operator",
            expected_state_version=0,
        )


def test_blocked_by_data_quality_candidate_can_be_archived(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    blocked = block_pattern_candidate_for_data_quality(
        candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=candidate.state_version,
    )
    archived = archive_pattern_candidate(
        candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=blocked.state_version,
    )
    assert archived.lifecycle_state == "archived"


def test_classify_accepts_invalid_leakage_and_it_is_archivable(isolated_database: Path) -> None:
    _prepare(isolated_database)
    candidate = _register()
    _mark_evaluated(candidate.candidate_id)
    evaluated = get_pattern_candidate(candidate.candidate_id)
    classified = classify_pattern_candidate(
        candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=evaluated.state_version, next_lifecycle_state="invalid_leakage",
    )
    assert classified.lifecycle_state == "invalid_leakage"
    archived = archive_pattern_candidate(
        candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=classified.state_version,
    )
    assert archived.lifecycle_state == "archived"
