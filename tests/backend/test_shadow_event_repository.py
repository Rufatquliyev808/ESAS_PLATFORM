from pathlib import Path
import sqlite3

import pytest

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.shadow_event_repository import (
    list_shadow_run_events,
    record_shadow_event,
)
from backend.app.database.shadow_run_repository import ShadowRunNotFoundError, register_shadow_run


def _prepare(database_path: Path) -> None:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")


def _register_run():
    return register_shadow_run(
        created_by="TEST-USER", planned_end_at="2026-09-01T00:00:00+00:00",
        code_commit="abc123", config_hash="sha256:config",
        feature_claim_versions=("market_structure:1.0.0",), symbols=("GOLD",), timeframes=("M5",),
        sessions=("london",), accepted_market_regimes=("trending",),
        minimum_market_open_duration_seconds=3600, minimum_eligible_decision_count=30,
        primary_metric="net_return_percent", primary_metric_threshold=0.5,
        secondary_metrics={}, failure_rules={}, theoretical_fill_model={}, risk_budget={},
        data_quality_policy={}, approved_by="RISK-OFFICER", rollback_plan="halt and archive run",
        participants=(("champion", "structure_break_long", "1.0.0"),),
    )


def test_record_shadow_event_persists_and_hashes_payload(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register_run()
    event = record_shadow_event(
        shadow_run_id=run.shadow_run_id, event_type="SHADOW_RUN_STARTED",
        correlation_id="corr-1", actor="TEST-USER", payload={"note": "manual start"},
    )
    assert event.payload == {"note": "manual start"}
    assert event.payload_hash.startswith("sha256:")


def test_rejects_unsupported_event_type(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register_run()
    with pytest.raises(ValueError):
        record_shadow_event(
            shadow_run_id=run.shadow_run_id, event_type="ORDER_PLACED",
            correlation_id="corr-1", actor="TEST-USER", payload={},
        )


def test_rejects_payload_with_reserved_broker_fields(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register_run()
    with pytest.raises(ValueError):
        record_shadow_event(
            shadow_run_id=run.shadow_run_id, event_type="SHADOW_DECISION_RECORDED",
            correlation_id="corr-1", actor="TEST-USER", payload={"order_id": "123"},
        )
    with pytest.raises(ValueError):
        record_shadow_event(
            shadow_run_id=run.shadow_run_id, event_type="SHADOW_DECISION_RECORDED",
            correlation_id="corr-1", actor="TEST-USER", payload={"mt5_ticket": "999"},
        )


def test_rejects_event_for_missing_run(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with pytest.raises(ShadowRunNotFoundError):
        record_shadow_event(
            shadow_run_id="missing", event_type="SHADOW_RUN_STARTED",
            correlation_id="corr-1", actor="TEST-USER", payload={},
        )


def test_list_shadow_run_events_is_chronological(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register_run()
    first = record_shadow_event(
        shadow_run_id=run.shadow_run_id, event_type="SHADOW_RUN_STARTED",
        correlation_id="corr-1", actor="TEST-USER", payload={},
    )
    second = record_shadow_event(
        shadow_run_id=run.shadow_run_id, event_type="SHADOW_DECISION_RECORDED",
        correlation_id="corr-2", actor="TEST-USER", payload={"symbol": "GOLD"},
    )
    events = list_shadow_run_events(run.shadow_run_id)
    assert [event.event_id for event in events] == [first.event_id, second.event_id]


def test_shadow_events_are_append_only(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register_run()
    event = record_shadow_event(
        shadow_run_id=run.shadow_run_id, event_type="SHADOW_RUN_STARTED",
        correlation_id="corr-1", actor="TEST-USER", payload={},
    )
    with get_connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE shadow_events SET actor = 'someone-else' WHERE event_id = ?;",
                (event.event_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM shadow_events WHERE event_id = ?;",
                (event.event_id,),
            )
