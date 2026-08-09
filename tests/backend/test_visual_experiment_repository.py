from pathlib import Path

import pytest

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.visual_experiment_repository import (
    VisualExperimentConflictError,
    VisualExperimentListPosition,
    VisualExperimentNotFoundError,
    VisualExperimentOwnershipError,
    archive_visual_experiment,
    get_visual_experiment,
    list_visual_experiments,
    register_visual_experiment,
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


def _register(
    session_id: str = "rps_test", created_by: str = "TEST-USER", *,
    label_spec_id: str = "sha256:label", train_end_at: str = "2026-08-06T00:00:00+00:00",
    validation_end_at: str = "2026-08-07T00:00:00+00:00",
):
    return register_visual_experiment(
        created_by=created_by, actor_role="operator", replay_session_id=session_id,
        symbol="GOLD", timeframe="M1", source_bar_fingerprint="sha256:bars",
        render_spec_id="sha256:render", label_spec_id=label_spec_id,
        observation_window_bars=64, train_end_at=train_end_at, validation_end_at=validation_end_at,
    )


def test_register_persists_experiment_with_registered_state(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    assert experiment.lifecycle_state == "registered"
    assert experiment.state_version == 0
    assert experiment.symbol == "GOLD"
    assert experiment.timeframe == "M1"
    fetched = get_visual_experiment(experiment.experiment_id)
    assert fetched == experiment

    with get_connection() as connection:
        audit = connection.execute(
            "SELECT action, previous_state, next_state FROM visual_experiment_audit WHERE experiment_id = ?;",
            (experiment.experiment_id,),
        ).fetchall()
    assert len(audit) == 1
    assert audit[0]["action"] == "register"
    assert audit[0]["previous_state"] is None
    assert audit[0]["next_state"] == "registered"


def test_registration_is_idempotent_for_identical_configuration(isolated_database: Path) -> None:
    _prepare(isolated_database)
    first = _register()
    second = _register()
    assert first.experiment_id == second.experiment_id
    with get_connection() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS n FROM visual_experiments WHERE experiment_id = ?;",
            (first.experiment_id,),
        ).fetchone()["n"]
    assert count == 1


def test_different_configuration_yields_different_experiment_id(isolated_database: Path) -> None:
    _prepare(isolated_database)
    first = _register(label_spec_id="sha256:label_a")
    second = _register(label_spec_id="sha256:label_b")
    assert first.experiment_id != second.experiment_id


def test_registration_by_different_owner_conflicts(isolated_database: Path) -> None:
    _prepare(isolated_database, session_id="rps_test", created_by="TEST-USER")
    _prepare(isolated_database, session_id="rps_other", created_by="OTHER-USER")
    _register()
    with pytest.raises(VisualExperimentOwnershipError):
        _register(session_id="rps_other", created_by="OTHER-USER")


def test_rejects_unknown_timeframe(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with pytest.raises(ValueError):
        register_visual_experiment(
            created_by="TEST-USER", actor_role="operator", replay_session_id="rps_test",
            symbol="GOLD", timeframe="M3", source_bar_fingerprint="sha256:bars",
            render_spec_id="sha256:render", label_spec_id="sha256:label",
            observation_window_bars=64, train_end_at="2026-08-06T00:00:00+00:00",
            validation_end_at="2026-08-07T00:00:00+00:00",
        )


def test_rejects_non_positive_observation_window_bars(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with pytest.raises(ValueError):
        register_visual_experiment(
            created_by="TEST-USER", actor_role="operator", replay_session_id="rps_test",
            symbol="GOLD", timeframe="M1", source_bar_fingerprint="sha256:bars",
            render_spec_id="sha256:render", label_spec_id="sha256:label",
            observation_window_bars=0, train_end_at="2026-08-06T00:00:00+00:00",
            validation_end_at="2026-08-07T00:00:00+00:00",
        )


def test_rejects_validation_end_at_not_after_train_end_at(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with pytest.raises(ValueError):
        _register(train_end_at="2026-08-07T00:00:00+00:00", validation_end_at="2026-08-06T00:00:00+00:00")


def test_get_unknown_experiment_raises_not_found(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with pytest.raises(VisualExperimentNotFoundError):
        get_visual_experiment("sha256:does-not-exist")


def test_archive_transitions_from_registered(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    archived = archive_visual_experiment(
        experiment_id=experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=experiment.state_version,
    )
    assert archived.lifecycle_state == "archived"
    assert archived.state_version == experiment.state_version + 1


def test_archive_rejects_stale_state_version(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    with pytest.raises(VisualExperimentConflictError):
        archive_visual_experiment(
            experiment_id=experiment.experiment_id, actor="TEST-USER", actor_role="operator",
            expected_state_version=experiment.state_version + 1,
        )


def test_archive_twice_conflicts(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    archived = archive_visual_experiment(
        experiment_id=experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=experiment.state_version,
    )
    with pytest.raises(VisualExperimentConflictError):
        archive_visual_experiment(
            experiment_id=experiment.experiment_id, actor="TEST-USER", actor_role="operator",
            expected_state_version=archived.state_version,
        )


def test_list_returns_only_owners_experiments_newest_first(isolated_database: Path) -> None:
    _prepare(isolated_database, session_id="rps_test", created_by="TEST-USER")
    _prepare(isolated_database, session_id="rps_other", created_by="OTHER-USER")
    first = _register(train_end_at="2026-08-06T00:00:00+00:00", validation_end_at="2026-08-07T00:00:00+00:00")
    second = _register(label_spec_id="sha256:label_b", train_end_at="2026-08-06T00:00:00+00:00", validation_end_at="2026-08-07T00:00:00+00:00")
    _register(session_id="rps_other", created_by="OTHER-USER", label_spec_id="sha256:label_c")

    page = list_visual_experiments(owner="TEST-USER")
    ids = {item.experiment_id for item in page.items}
    assert ids == {first.experiment_id, second.experiment_id}
    assert page.next_position is None


def test_list_paginates_with_cursor(isolated_database: Path) -> None:
    _prepare(isolated_database)
    _register(label_spec_id="sha256:label_a")
    _register(label_spec_id="sha256:label_b")

    first_page = list_visual_experiments(owner="TEST-USER", page_size=1)
    assert len(first_page.items) == 1
    assert first_page.next_position is not None

    second_page = list_visual_experiments(
        owner="TEST-USER", page_size=1, after=first_page.next_position,
    )
    assert len(second_page.items) == 1
    assert second_page.items[0].experiment_id != first_page.items[0].experiment_id


def test_archive_by_another_user_is_rejected(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    with pytest.raises(VisualExperimentOwnershipError):
        archive_visual_experiment(
            experiment_id=experiment.experiment_id, actor="OTHER-USER", actor_role="operator",
            expected_state_version=experiment.state_version,
        )
