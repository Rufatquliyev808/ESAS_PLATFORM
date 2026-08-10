from pathlib import Path

import pytest

from backend.app.analysis.visual_label import LabelSpec
from backend.app.analysis.visual_render import RenderSpec
from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.visual_experiment_repository import (
    VisualExperimentConflictError,
    VisualExperimentListPosition,
    VisualExperimentNotFoundError,
    VisualExperimentOwnershipError,
    archive_visual_experiment,
    block_experiment_for_data_quality,
    get_visual_experiment,
    list_visual_experiments,
    mark_accepted_for_shadow,
    mark_evaluated,
    mark_insufficient_evidence,
    mark_out_of_distribution,
    mark_rejected,
    mark_rendering_failed,
    register_visual_experiment,
    start_rendering,
    start_training,
)


DEFAULT_RENDER_SPEC = RenderSpec()
DEFAULT_LABEL_SPEC = LabelSpec(horizon_bars=10, up_threshold_bps=10.0, down_threshold_bps=-10.0)


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
    label_spec: LabelSpec = DEFAULT_LABEL_SPEC,
    train_end_at: str = "2026-08-06T00:00:00+00:00",
    validation_end_at: str = "2026-08-07T00:00:00+00:00",
):
    return register_visual_experiment(
        created_by=created_by, actor_role="operator", replay_session_id=session_id,
        symbol="GOLD", timeframe="M1", source_bar_fingerprint="sha256:bars",
        render_spec=DEFAULT_RENDER_SPEC, label_spec=label_spec,
        observation_window_bars=64, train_end_at=train_end_at, validation_end_at=validation_end_at,
    )


def test_register_persists_experiment_with_registered_state(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    assert experiment.lifecycle_state == "registered"
    assert experiment.state_version == 0
    assert experiment.symbol == "GOLD"
    assert experiment.timeframe == "M1"
    assert experiment.render_spec["width"] == DEFAULT_RENDER_SPEC.width
    assert experiment.label_spec["horizon_bars"] == DEFAULT_LABEL_SPEC.horizon_bars
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
    first = _register(label_spec=LabelSpec(10, 10.0, -10.0))
    second = _register(label_spec=LabelSpec(20, 10.0, -10.0))
    assert first.experiment_id != second.experiment_id
    assert first.render_spec_id == second.render_spec_id
    assert first.label_spec_id != second.label_spec_id


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
            render_spec=DEFAULT_RENDER_SPEC, label_spec=DEFAULT_LABEL_SPEC,
            observation_window_bars=64, train_end_at="2026-08-06T00:00:00+00:00",
            validation_end_at="2026-08-07T00:00:00+00:00",
        )


def test_rejects_non_positive_observation_window_bars(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with pytest.raises(ValueError):
        register_visual_experiment(
            created_by="TEST-USER", actor_role="operator", replay_session_id="rps_test",
            symbol="GOLD", timeframe="M1", source_bar_fingerprint="sha256:bars",
            render_spec=DEFAULT_RENDER_SPEC, label_spec=DEFAULT_LABEL_SPEC,
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
    first = _register(label_spec=LabelSpec(10, 10.0, -10.0))
    second = _register(label_spec=LabelSpec(20, 10.0, -10.0))
    _register(session_id="rps_other", created_by="OTHER-USER", label_spec=LabelSpec(30, 10.0, -10.0))

    page = list_visual_experiments(owner="TEST-USER")
    ids = {item.experiment_id for item in page.items}
    assert ids == {first.experiment_id, second.experiment_id}
    assert page.next_position is None


def test_list_paginates_with_cursor(isolated_database: Path) -> None:
    _prepare(isolated_database)
    _register(label_spec=LabelSpec(10, 10.0, -10.0))
    _register(label_spec=LabelSpec(20, 10.0, -10.0))

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


def test_start_rendering_transitions_from_registered(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    rendering = start_rendering(
        experiment_id=experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=experiment.state_version,
    )
    assert rendering.lifecycle_state == "rendering"
    assert rendering.state_version == experiment.state_version + 1

    with get_connection() as connection:
        audit = connection.execute(
            "SELECT action, previous_state, next_state FROM visual_experiment_audit "
            "WHERE experiment_id = ? ORDER BY audit_id DESC LIMIT 1;",
            (experiment.experiment_id,),
        ).fetchone()
    assert audit["action"] == "start_rendering"
    assert audit["previous_state"] == "registered"
    assert audit["next_state"] == "rendering"


def test_start_rendering_rejects_non_registered_state(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    archived = archive_visual_experiment(
        experiment_id=experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=experiment.state_version,
    )
    with pytest.raises(VisualExperimentConflictError):
        start_rendering(
            experiment_id=archived.experiment_id, actor="TEST-USER", actor_role="operator",
            expected_state_version=archived.state_version,
        )


def test_start_rendering_by_another_user_is_rejected(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    with pytest.raises(VisualExperimentOwnershipError):
        start_rendering(
            experiment_id=experiment.experiment_id, actor="OTHER-USER", actor_role="operator",
            expected_state_version=experiment.state_version,
        )


def test_mark_rendering_failed_transitions_from_rendering(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    rendering = start_rendering(
        experiment_id=experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=experiment.state_version,
    )
    failed = mark_rendering_failed(
        experiment_id=rendering.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=rendering.state_version,
    )
    assert failed.lifecycle_state == "failed"
    assert failed.state_version == rendering.state_version + 1


def test_mark_rendering_failed_rejects_from_registered(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    with pytest.raises(VisualExperimentConflictError):
        mark_rendering_failed(
            experiment_id=experiment.experiment_id, actor="TEST-USER", actor_role="operator",
            expected_state_version=experiment.state_version,
        )


def test_start_training_transitions_from_rendering(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    rendering = start_rendering(
        experiment_id=experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=experiment.state_version,
    )
    training = start_training(
        experiment_id=rendering.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=rendering.state_version,
    )
    assert training.lifecycle_state == "training"
    assert training.state_version == rendering.state_version + 1

    with get_connection() as connection:
        audit = connection.execute(
            "SELECT action, previous_state, next_state FROM visual_experiment_audit "
            "WHERE experiment_id = ? ORDER BY audit_id DESC LIMIT 1;",
            (experiment.experiment_id,),
        ).fetchone()
    assert audit["action"] == "start_training"
    assert audit["previous_state"] == "rendering"
    assert audit["next_state"] == "training"


def test_start_training_rejects_from_registered(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    with pytest.raises(VisualExperimentConflictError):
        start_training(
            experiment_id=experiment.experiment_id, actor="TEST-USER", actor_role="operator",
            expected_state_version=experiment.state_version,
        )


def test_start_training_by_another_user_is_rejected(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    rendering = start_rendering(
        experiment_id=experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=experiment.state_version,
    )
    with pytest.raises(VisualExperimentOwnershipError):
        start_training(
            experiment_id=rendering.experiment_id, actor="OTHER-USER", actor_role="operator",
            expected_state_version=rendering.state_version,
        )


def test_block_experiment_for_data_quality_transitions_from_rendering(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    rendering = start_rendering(
        experiment_id=experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=experiment.state_version,
    )
    blocked = block_experiment_for_data_quality(
        experiment_id=rendering.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=rendering.state_version,
    )
    assert blocked.lifecycle_state == "blocked_by_data_quality"
    assert blocked.state_version == rendering.state_version + 1

    with get_connection() as connection:
        audit = connection.execute(
            "SELECT action, previous_state, next_state FROM visual_experiment_audit "
            "WHERE experiment_id = ? ORDER BY audit_id DESC LIMIT 1;",
            (experiment.experiment_id,),
        ).fetchone()
    assert audit["action"] == "block_for_data_quality"
    assert audit["previous_state"] == "rendering"
    assert audit["next_state"] == "blocked_by_data_quality"


def test_block_experiment_for_data_quality_rejects_from_registered(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    with pytest.raises(VisualExperimentConflictError):
        block_experiment_for_data_quality(
            experiment_id=experiment.experiment_id, actor="TEST-USER", actor_role="operator",
            expected_state_version=experiment.state_version,
        )


def _rendering_then_training(experiment):
    rendering = start_rendering(
        experiment_id=experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=experiment.state_version,
    )
    return start_training(
        experiment_id=rendering.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=rendering.state_version,
    )


def test_mark_evaluated_transitions_from_training(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    training = _rendering_then_training(experiment)
    evaluated = mark_evaluated(
        experiment_id=training.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=training.state_version,
    )
    assert evaluated.lifecycle_state == "evaluated"
    assert evaluated.state_version == training.state_version + 1

    with get_connection() as connection:
        audit = connection.execute(
            "SELECT action, previous_state, next_state FROM visual_experiment_audit "
            "WHERE experiment_id = ? ORDER BY audit_id DESC LIMIT 1;",
            (experiment.experiment_id,),
        ).fetchone()
    assert audit["action"] == "mark_evaluated"
    assert audit["previous_state"] == "training"
    assert audit["next_state"] == "evaluated"


def test_mark_evaluated_rejects_from_rendering(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    rendering = start_rendering(
        experiment_id=experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=experiment.state_version,
    )
    with pytest.raises(VisualExperimentConflictError):
        mark_evaluated(
            experiment_id=rendering.experiment_id, actor="TEST-USER", actor_role="operator",
            expected_state_version=rendering.state_version,
        )


def test_mark_out_of_distribution_transitions_from_training(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    training = _rendering_then_training(experiment)
    result = mark_out_of_distribution(
        experiment_id=training.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=training.state_version,
    )
    assert result.lifecycle_state == "out_of_distribution"


def test_mark_insufficient_evidence_transitions_from_training(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    training = _rendering_then_training(experiment)
    result = mark_insufficient_evidence(
        experiment_id=training.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=training.state_version,
    )
    assert result.lifecycle_state == "insufficient_evidence"


def test_mark_insufficient_evidence_by_another_user_is_rejected(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    training = _rendering_then_training(experiment)
    with pytest.raises(VisualExperimentOwnershipError):
        mark_insufficient_evidence(
            experiment_id=training.experiment_id, actor="OTHER-USER", actor_role="operator",
            expected_state_version=training.state_version,
        )


def test_mark_accepted_for_shadow_transitions_from_evaluated(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    training = _rendering_then_training(experiment)
    evaluated = mark_evaluated(
        experiment_id=training.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=training.state_version,
    )
    accepted = mark_accepted_for_shadow(
        experiment_id=evaluated.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=evaluated.state_version,
    )
    assert accepted.lifecycle_state == "accepted_for_shadow"
    assert accepted.state_version == evaluated.state_version + 1

    with get_connection() as connection:
        audit = connection.execute(
            "SELECT action, previous_state, next_state FROM visual_experiment_audit "
            "WHERE experiment_id = ? ORDER BY audit_id DESC LIMIT 1;",
            (experiment.experiment_id,),
        ).fetchone()
    assert audit["action"] == "mark_accepted_for_shadow"
    assert audit["previous_state"] == "evaluated"
    assert audit["next_state"] == "accepted_for_shadow"


def test_mark_rejected_transitions_from_evaluated(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    training = _rendering_then_training(experiment)
    evaluated = mark_evaluated(
        experiment_id=training.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=training.state_version,
    )
    rejected = mark_rejected(
        experiment_id=evaluated.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=evaluated.state_version,
    )
    assert rejected.lifecycle_state == "rejected"


def test_mark_accepted_for_shadow_rejects_from_training(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    training = _rendering_then_training(experiment)
    with pytest.raises(VisualExperimentConflictError):
        mark_accepted_for_shadow(
            experiment_id=training.experiment_id, actor="TEST-USER", actor_role="operator",
            expected_state_version=training.state_version,
        )


def test_mark_rejected_by_another_user_is_rejected(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register()
    training = _rendering_then_training(experiment)
    evaluated = mark_evaluated(
        experiment_id=training.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=training.state_version,
    )
    with pytest.raises(VisualExperimentOwnershipError):
        mark_rejected(
            experiment_id=evaluated.experiment_id, actor="OTHER-USER", actor_role="operator",
            expected_state_version=evaluated.state_version,
        )
