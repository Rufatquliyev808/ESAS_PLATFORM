from pathlib import Path
import sqlite3

import pytest

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.shadow_run_repository import (
    ShadowRunConflictError,
    ShadowRunNotFoundError,
    ShadowRunOwnershipError,
    complete_shadow_run,
    get_shadow_run,
    halt_shadow_run,
    register_shadow_run,
    start_shadow_run,
)


def _prepare(database_path: Path) -> None:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")


def _register(**overrides):
    defaults = dict(
        created_by="TEST-USER", planned_end_at="2026-09-01T00:00:00+00:00",
        code_commit="abc123", config_hash="sha256:config",
        feature_claim_versions=("market_structure:1.0.0", "liquidity_sweep:1.0.0"),
        symbols=("GOLD",), timeframes=("M5",), sessions=("london",),
        accepted_market_regimes=("trending", "ranging"),
        minimum_market_open_duration_seconds=3600, minimum_eligible_decision_count=30,
        primary_metric="net_return_percent", primary_metric_threshold=0.5,
        secondary_metrics={"max_drawdown_percent": 5.0}, failure_rules={"max_tail_loss_percent": 10.0},
        theoretical_fill_model={"spread_bps": 2.0, "latency_ms": 50},
        risk_budget={"max_concurrent_positions": 3}, data_quality_policy={"max_gap_seconds": 5},
        approved_by="RISK-OFFICER", rollback_plan="halt and archive run",
        participants=(("champion", "structure_break_long", "1.0.0"), ("challenger", "market_structure_long", "1.0.0")),
    )
    defaults.update(overrides)
    return register_shadow_run(**defaults)


def test_register_shadow_run_persists_full_manifest_and_participants(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    assert run.state == "registered"
    assert run.execution_allowed is False
    assert run.state_version == 0
    assert len(run.participants) == 2
    champion = next(p for p in run.participants if p.role == "champion")
    assert champion.module_id == "structure_break_long"


def test_register_requires_exactly_one_champion(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with pytest.raises(ValueError):
        _register(participants=(("challenger", "a", "1.0.0"),))
    with pytest.raises(ValueError):
        _register(participants=(("champion", "a", "1.0.0"), ("champion", "b", "1.0.0")))


def test_register_rejects_invalid_thresholds(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with pytest.raises(ValueError):
        _register(minimum_market_open_duration_seconds=-1)
    with pytest.raises(ValueError):
        _register(minimum_eligible_decision_count=0)


def test_get_shadow_run_round_trips(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    reloaded = get_shadow_run(run.shadow_run_id)
    assert reloaded == run


def test_get_missing_shadow_run_raises(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with pytest.raises(ShadowRunNotFoundError):
        get_shadow_run("missing")


def test_lifecycle_registered_to_started_to_completed(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    started = start_shadow_run(shadow_run_id=run.shadow_run_id, actor="TEST-USER", expected_state_version=run.state_version)
    assert started.state == "started"
    completed = complete_shadow_run(shadow_run_id=run.shadow_run_id, actor="TEST-USER", expected_state_version=started.state_version)
    assert completed.state == "completed"


def test_cannot_complete_before_starting(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    with pytest.raises(ShadowRunConflictError):
        complete_shadow_run(shadow_run_id=run.shadow_run_id, actor="TEST-USER", expected_state_version=run.state_version)


def test_halt_is_reachable_from_registered_or_started(isolated_database: Path) -> None:
    _prepare(isolated_database)
    registered_run = _register()
    halted_from_registered = halt_shadow_run(
        shadow_run_id=registered_run.shadow_run_id, actor="TEST-USER",
        expected_state_version=registered_run.state_version, reason="order adapter call attempted",
    )
    assert halted_from_registered.state == "halted"
    assert halted_from_registered.halt_reason == "order adapter call attempted"

    started_run = _register()
    started = start_shadow_run(shadow_run_id=started_run.shadow_run_id, actor="TEST-USER", expected_state_version=started_run.state_version)
    halted_from_started = halt_shadow_run(
        shadow_run_id=started.shadow_run_id, actor="TEST-USER",
        expected_state_version=started.state_version, reason="critical safety event",
    )
    assert halted_from_started.state == "halted"


def test_cannot_transition_terminal_run(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    halted = halt_shadow_run(shadow_run_id=run.shadow_run_id, actor="TEST-USER", expected_state_version=run.state_version, reason="x")
    with pytest.raises(ShadowRunConflictError):
        start_shadow_run(shadow_run_id=halted.shadow_run_id, actor="TEST-USER", expected_state_version=halted.state_version)


def test_transition_enforces_ownership_and_optimistic_lock(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    with pytest.raises(ShadowRunOwnershipError):
        start_shadow_run(shadow_run_id=run.shadow_run_id, actor="OTHER-USER", expected_state_version=run.state_version)
    with pytest.raises(ShadowRunConflictError):
        start_shadow_run(shadow_run_id=run.shadow_run_id, actor="TEST-USER", expected_state_version=run.state_version + 1)


def test_execution_allowed_cannot_be_forced_true_at_the_database_level(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    with get_connection() as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE shadow_runs SET execution_allowed = 1 WHERE shadow_run_id = ?;",
                (run.shadow_run_id,),
            )


def test_manifest_fields_are_immutable_once_registered(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    with get_connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE shadow_runs SET primary_metric_threshold = 99.0 WHERE shadow_run_id = ?;",
                (run.shadow_run_id,),
            )


def test_shadow_run_participants_are_append_only(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    participant_id = run.participants[0].participant_id
    with get_connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE shadow_run_participants SET module_version = '2.0.0' WHERE participant_id = ?;",
                (participant_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM shadow_run_participants WHERE participant_id = ?;",
                (participant_id,),
            )
