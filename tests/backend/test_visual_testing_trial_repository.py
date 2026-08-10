from pathlib import Path

import pytest

from backend.app.analysis.visual_label import LabelSpec
from backend.app.analysis.visual_render import RenderSpec
from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.visual_experiment_repository import register_visual_experiment
from backend.app.database.visual_testing_trial_repository import (
    VisualTestingTrialConflictError,
    compute_trial_id,
    count_family_trials,
    get_trial,
    register_trial,
    trial_is_registered,
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


def _register_experiment(session_id: str = "rps_test", created_by: str = "TEST-USER", *, source_bar_fingerprint: str = "sha256:bars"):
    return register_visual_experiment(
        created_by=created_by, actor_role="operator", replay_session_id=session_id,
        symbol="GOLD", timeframe="M1", source_bar_fingerprint=source_bar_fingerprint,
        render_spec=DEFAULT_RENDER_SPEC, label_spec=DEFAULT_LABEL_SPEC,
        observation_window_bars=64, train_end_at="2026-08-06T00:00:00+00:00",
        validation_end_at="2026-08-07T00:00:00+00:00",
    )


def test_register_trial_persists_and_returns_it(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register_experiment()
    trial = register_trial(
        testing_family_id="sha256:family-a", experiment_id=experiment.experiment_id,
        model_spec_id="sha256:model-spec-a", training_spec_id="sha256:training-spec-a",
    )
    assert trial.testing_family_id == "sha256:family-a"
    fetched = get_trial(trial.trial_id)
    assert fetched == trial


def test_register_trial_is_idempotent_for_identical_trial(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register_experiment()
    first = register_trial(
        testing_family_id="sha256:family-a", experiment_id=experiment.experiment_id,
        model_spec_id="sha256:model-spec-a", training_spec_id="sha256:training-spec-a",
    )
    second = register_trial(
        testing_family_id="sha256:family-a", experiment_id=experiment.experiment_id,
        model_spec_id="sha256:model-spec-a", training_spec_id="sha256:training-spec-a",
    )
    assert first == second
    assert count_family_trials("sha256:family-a") == 1


def test_register_trial_conflicts_on_different_experiment_for_same_trial_identity(
    isolated_database: Path,
) -> None:
    _prepare(isolated_database)
    experiment_a = _register_experiment(source_bar_fingerprint="sha256:bars-a")
    experiment_b = _register_experiment(source_bar_fingerprint="sha256:bars-b")
    register_trial(
        testing_family_id="sha256:family-a", experiment_id=experiment_a.experiment_id,
        model_spec_id="sha256:model-spec-a", training_spec_id="sha256:training-spec-a",
    )
    with pytest.raises(VisualTestingTrialConflictError):
        register_trial(
            testing_family_id="sha256:family-a", experiment_id=experiment_b.experiment_id,
            model_spec_id="sha256:model-spec-a", training_spec_id="sha256:training-spec-a",
        )


def test_count_family_trials_counts_distinct_model_training_spec_combinations(
    isolated_database: Path,
) -> None:
    _prepare(isolated_database)
    experiment_a = _register_experiment(source_bar_fingerprint="sha256:bars-a")
    experiment_b = _register_experiment(source_bar_fingerprint="sha256:bars-b")
    register_trial(
        testing_family_id="sha256:family-a", experiment_id=experiment_a.experiment_id,
        model_spec_id="sha256:model-spec-1", training_spec_id="sha256:training-spec-1",
    )
    register_trial(
        testing_family_id="sha256:family-a", experiment_id=experiment_a.experiment_id,
        model_spec_id="sha256:model-spec-2", training_spec_id="sha256:training-spec-1",
    )
    register_trial(
        testing_family_id="sha256:family-OTHER", experiment_id=experiment_b.experiment_id,
        model_spec_id="sha256:model-spec-1", training_spec_id="sha256:training-spec-1",
    )
    assert count_family_trials("sha256:family-a") == 2
    assert count_family_trials("sha256:family-OTHER") == 1


def test_count_family_trials_with_no_trials_is_zero(isolated_database: Path) -> None:
    _prepare(isolated_database)
    assert count_family_trials("sha256:never-registered") == 0


def test_trial_is_registered_reflects_registry_state(isolated_database: Path) -> None:
    _prepare(isolated_database)
    experiment = _register_experiment()
    assert trial_is_registered(
        testing_family_id="sha256:family-a", model_spec_id="sha256:m", training_spec_id="sha256:t",
    ) is False
    register_trial(
        testing_family_id="sha256:family-a", experiment_id=experiment.experiment_id,
        model_spec_id="sha256:m", training_spec_id="sha256:t",
    )
    assert trial_is_registered(
        testing_family_id="sha256:family-a", model_spec_id="sha256:m", training_spec_id="sha256:t",
    ) is True


def test_compute_trial_id_is_deterministic() -> None:
    id_a = compute_trial_id(
        testing_family_id="sha256:family-a", model_spec_id="sha256:m", training_spec_id="sha256:t",
    )
    id_b = compute_trial_id(
        testing_family_id="sha256:family-a", model_spec_id="sha256:m", training_spec_id="sha256:t",
    )
    assert id_a == id_b


def test_get_trial_returns_none_for_unknown_trial(isolated_database: Path) -> None:
    _prepare(isolated_database)
    assert get_trial("sha256:unknown-trial") is None
