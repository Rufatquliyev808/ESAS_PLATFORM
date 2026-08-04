from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.replay_session_repository import (
    ReplayTransitionConflictError,
    create_replay_session,
    process_replay_step,
    run_max_speed_replay,
    transition_replay_session,
)
from backend.app.replay.result_manifest import (
    ReplayManifestMismatchError,
    create_replay_result_manifest,
    prove_replay_reproduction,
)


BASE_TIME = datetime(2026, 8, 4, 18, 0, tzinfo=UTC)


def seed_ticks(database_path: Path, count: int = 11) -> None:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO tick_events
            (
                event_id, event_type, event_timestamp, source,
                event_version, symbol, bid, ask, last, volume, flags,
                source_time_msc, module_version, raw_event_json
            )
            VALUES (?, 'TICK_RECEIVED', ?, 'esas.mt5.bridge', '1.0',
                    'GOLD', 4100.0, 4100.5, 4100.25, 1, 6, ?,
                    '1.6.0', '{}');
            """,
            [
                (
                    f"GOLD:{index:04d}",
                    (BASE_TIME + timedelta(microseconds=index)).isoformat(
                        timespec="microseconds"
                    ),
                    index,
                )
                for index in range(1, count + 1)
            ],
        )


def create_running(mode: str):
    created = create_replay_session(
        created_by="TEST-USER",
        actor_role="operator",
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(seconds=1),
        mode=mode,
    )
    return transition_replay_session(
        session_id=created.session_id,
        actor="TEST-USER",
        actor_role="operator",
        action="start",
        expected_state="created",
    )


def complete_max_speed(batch_size: int):
    session = create_running("max_speed")
    result = run_max_speed_replay(
        session_id=session.session_id,
        actor="REPLAY-WORKER",
        actor_role="worker",
        batch_size=batch_size,
    )
    assert result.state == "completed"
    return session


def test_max_speed_manifests_are_batch_size_independent(
    isolated_database: Path,
) -> None:
    seed_ticks(isolated_database)
    first = complete_max_speed(2)
    second = complete_max_speed(7)

    first_manifest = create_replay_result_manifest(
        session_id=first.session_id, batch_size=3
    )
    second_manifest = create_replay_result_manifest(
        session_id=second.session_id, batch_size=5
    )
    proof = prove_replay_reproduction(first_manifest, second_manifest)

    assert first_manifest.result_tick_count == 11
    assert first_manifest.result_fingerprint == second_manifest.result_fingerprint
    assert proof.result_fingerprint == first_manifest.result_fingerprint


def test_step_session_produces_completed_manifest(
    isolated_database: Path,
) -> None:
    seed_ticks(isolated_database, count=5)
    session = create_running("step")
    process_replay_step(
        session_id=session.session_id,
        actor="TEST-USER",
        actor_role="operator",
        idempotency_key="step-1",
        requested_ticks=2,
    )
    process_replay_step(
        session_id=session.session_id,
        actor="TEST-USER",
        actor_role="operator",
        idempotency_key="step-2",
        requested_ticks=3,
    )

    manifest = create_replay_result_manifest(session_id=session.session_id)

    assert manifest.mode == "step"
    assert manifest.result_tick_count == 5
    assert manifest.last_position.event_id == "GOLD:0005"


def test_incomplete_session_cannot_produce_final_manifest(
    isolated_database: Path,
) -> None:
    seed_ticks(isolated_database)
    session = create_running("max_speed")

    with pytest.raises(ReplayTransitionConflictError, match="completed"):
        create_replay_result_manifest(session_id=session.session_id)


def test_changed_dataset_is_rejected(isolated_database: Path) -> None:
    seed_ticks(isolated_database)
    session = complete_max_speed(4)
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM tick_events WHERE event_id = 'GOLD:0005';"
        )
        connection.execute(
            """
            INSERT INTO tick_events
            (
                event_id, event_type, event_timestamp, source,
                event_version, symbol, bid, ask, last, volume, flags,
                source_time_msc, module_version, raw_event_json
            )
            VALUES ('GOLD:CHANGED', 'TICK_RECEIVED', ?,
                    'esas.mt5.bridge', '1.0', 'GOLD', 4100.0, 4100.5,
                    4100.25, 1, 6, 5, '1.6.0', '{}');
            """,
            (
                (BASE_TIME + timedelta(microseconds=5)).isoformat(
                    timespec="microseconds"
                ),
            ),
        )

    with pytest.raises(ReplayTransitionConflictError, match="no longer matches"):
        create_replay_result_manifest(session_id=session.session_id)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dataset_fingerprint", "sha256:different"),
        ("replay_contract_version", "2.0"),
        ("start_at", "2026-08-04T17:00:00.000000+00:00"),
        ("mode", "step"),
    ],
)
def test_incompatible_manifests_fail_closed(
    isolated_database: Path,
    field: str,
    value: str,
) -> None:
    seed_ticks(isolated_database)
    first = complete_max_speed(4)
    second = complete_max_speed(6)
    first_manifest = create_replay_result_manifest(session_id=first.session_id)
    second_manifest = create_replay_result_manifest(session_id=second.session_id)

    with pytest.raises(ReplayManifestMismatchError, match=field):
        prove_replay_reproduction(
            first_manifest,
            replace(second_manifest, **{field: value}),
        )
