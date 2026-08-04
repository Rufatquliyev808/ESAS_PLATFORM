from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.tick_replay_repository import TickPosition
from backend.app.replay.dataset_snapshot import (
    DATASET_FINGERPRINT_VERSION,
    EMPTY_DATASET_FINGERPRINT,
    create_dataset_snapshot,
)


BASE_TIME = datetime(2026, 8, 3, 8, 0, tzinfo=UTC)


def insert_tick(
    event_id: str,
    timestamp: datetime,
    *,
    symbol: str = "GOLD",
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO tick_events
            (
                event_id, event_type, event_timestamp, source, event_version,
                symbol, bid, ask, last, volume, flags, source_time_msc,
                module_version, raw_event_json
            )
            VALUES (?, 'TICK_RECEIVED', ?, 'esas.mt5.bridge', '1.0', ?,
                    4100.0, 4100.5, 4100.25, 1, 6, 1785744000000,
                    '1.6.0', '{}');
            """,
            (event_id, timestamp.isoformat(timespec="microseconds"), symbol),
        )


def expected_fingerprint(event_ids: list[str]) -> str:
    digest = sha256()
    for event_id in event_ids:
        encoded = event_id.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, byteorder="big"))
        digest.update(encoded)
    return f"sha256:{digest.hexdigest()}"


def test_snapshot_is_deterministic_and_uses_canonical_order() -> None:
    initialize_database()
    insert_tick("GOLD:3", BASE_TIME)
    insert_tick("GOLD:1", BASE_TIME)
    insert_tick("GOLD:2", BASE_TIME)

    query = {
        "symbol": "GOLD",
        "start_at": BASE_TIME,
        "end_at": BASE_TIME + timedelta(seconds=1),
        "batch_size": 2,
    }
    first = create_dataset_snapshot(**query)
    second = create_dataset_snapshot(**query)

    assert first == second
    assert first.tick_count == 3
    assert first.first_position == TickPosition(BASE_TIME, "GOLD:1")
    assert first.last_position == TickPosition(BASE_TIME, "GOLD:3")
    assert first.fingerprint == expected_fingerprint(
        ["GOLD:1", "GOLD:2", "GOLD:3"]
    )
    assert first.fingerprint_version == DATASET_FINGERPRINT_VERSION


def test_snapshot_respects_symbol_and_half_open_interval() -> None:
    initialize_database()
    insert_tick("BEFORE", BASE_TIME - timedelta(microseconds=1))
    insert_tick("START", BASE_TIME)
    insert_tick("MIDDLE", BASE_TIME + timedelta(seconds=1))
    insert_tick("END", BASE_TIME + timedelta(seconds=2))
    insert_tick("EURUSD:1", BASE_TIME, symbol="EURUSD")

    snapshot = create_dataset_snapshot(
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(seconds=2),
        batch_size=1,
    )

    assert snapshot.tick_count == 2
    assert snapshot.first_position == TickPosition(BASE_TIME, "START")
    assert snapshot.last_position == TickPosition(
        BASE_TIME + timedelta(seconds=1),
        "MIDDLE",
    )
    assert snapshot.fingerprint == expected_fingerprint(["START", "MIDDLE"])


def test_empty_snapshot_is_safe_and_deterministic() -> None:
    initialize_database()

    snapshot = create_dataset_snapshot(
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(seconds=1),
    )

    assert snapshot.tick_count == 0
    assert snapshot.first_position is None
    assert snapshot.last_position is None
    assert snapshot.fingerprint == EMPTY_DATASET_FINGERPRINT


def test_snapshot_does_not_change_raw_ticks() -> None:
    initialize_database()
    for index in range(5):
        insert_tick(
            f"GOLD:{index}",
            BASE_TIME + timedelta(milliseconds=index),
        )

    with get_connection() as connection:
        before = connection.execute(
            """
            SELECT event_id, event_timestamp, raw_event_json
            FROM tick_events
            ORDER BY event_id;
            """
        ).fetchall()

    snapshot = create_dataset_snapshot(
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(seconds=1),
        batch_size=2,
    )

    with get_connection() as connection:
        after = connection.execute(
            """
            SELECT event_id, event_timestamp, raw_event_json
            FROM tick_events
            ORDER BY event_id;
            """
        ).fetchall()

    assert snapshot.tick_count == 5
    assert [tuple(row) for row in after] == [tuple(row) for row in before]


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            {
                "symbol": " ",
                "start_at": BASE_TIME,
                "end_at": BASE_TIME + timedelta(seconds=1),
            },
            "symbol",
        ),
        (
            {
                "symbol": "GOLD",
                "start_at": BASE_TIME,
                "end_at": BASE_TIME,
            },
            "end_at",
        ),
        (
            {
                "symbol": "GOLD",
                "start_at": BASE_TIME,
                "end_at": BASE_TIME + timedelta(seconds=1),
                "batch_size": 0,
            },
            "batch_size",
        ),
    ],
)
def test_snapshot_validates_batch_and_query_inputs(
    arguments: dict[str, object],
    message: str,
) -> None:
    initialize_database()

    with pytest.raises(ValueError, match=message):
        create_dataset_snapshot(**arguments)
