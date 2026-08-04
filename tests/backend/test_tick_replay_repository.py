from datetime import UTC, datetime, timedelta

import pytest

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.tick_replay_repository import (
    TickPosition,
    read_tick_page,
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
                event_id,
                event_type,
                event_timestamp,
                source,
                event_version,
                symbol,
                bid,
                ask,
                last,
                volume,
                flags,
                source_time_msc,
                module_version,
                raw_event_json
            )
            VALUES (?, 'TICK_RECEIVED', ?, 'esas.mt5.bridge', '1.0', ?,
                    4100.0, 4100.5, 4100.25, 1, 6, 1785744000000,
                    '1.6.0', '{}');
            """,
            (event_id, timestamp.isoformat(timespec="microseconds"), symbol),
        )


def event_ids(page: object) -> list[str]:
    return [item.event_id for item in page.items]


def test_replay_order_is_deterministic_for_equal_timestamps() -> None:
    initialize_database()
    insert_tick("GOLD:3", BASE_TIME)
    insert_tick("GOLD:1", BASE_TIME)
    insert_tick("GOLD:2", BASE_TIME)

    query = {
        "symbol": "GOLD",
        "start_at": BASE_TIME,
        "end_at": BASE_TIME + timedelta(seconds=1),
    }
    first = read_tick_page(**query)
    second = read_tick_page(**query)

    assert event_ids(first) == ["GOLD:1", "GOLD:2", "GOLD:3"]
    assert event_ids(second) == event_ids(first)


def test_replay_interval_includes_start_and_excludes_end() -> None:
    initialize_database()
    insert_tick("BEFORE", BASE_TIME - timedelta(microseconds=1))
    insert_tick("START", BASE_TIME)
    insert_tick("MIDDLE", BASE_TIME + timedelta(seconds=1))
    insert_tick("END", BASE_TIME + timedelta(seconds=2))

    page = read_tick_page(
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(seconds=2),
    )

    assert event_ids(page) == ["START", "MIDDLE"]


def test_keyset_pages_have_no_gap_or_duplicate() -> None:
    initialize_database()
    for event_id in ("GOLD:1", "GOLD:2", "GOLD:3", "GOLD:4", "GOLD:5"):
        insert_tick(event_id, BASE_TIME)

    first = read_tick_page(
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(seconds=1),
        page_size=2,
    )
    assert first.has_more is True
    assert first.next_position == TickPosition(BASE_TIME, "GOLD:2")

    second = read_tick_page(
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(seconds=1),
        page_size=2,
        after=first.next_position,
    )
    third = read_tick_page(
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(seconds=1),
        page_size=2,
        after=second.next_position,
    )

    combined = event_ids(first) + event_ids(second) + event_ids(third)
    assert combined == ["GOLD:1", "GOLD:2", "GOLD:3", "GOLD:4", "GOLD:5"]
    assert len(combined) == len(set(combined))
    assert third.has_more is False
    assert third.next_position is None


def test_replay_is_symbol_scoped_and_empty_interval_is_safe() -> None:
    initialize_database()
    insert_tick("GOLD:1", BASE_TIME, symbol="GOLD")
    insert_tick("EURUSD:1", BASE_TIME, symbol="EURUSD")

    gold = read_tick_page(
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(seconds=1),
    )
    empty = read_tick_page(
        symbol="GOLD",
        start_at=BASE_TIME + timedelta(days=1),
        end_at=BASE_TIME + timedelta(days=2),
    )

    assert event_ids(gold) == ["GOLD:1"]
    assert empty.items == ()
    assert empty.has_more is False


def test_replay_validation_rejects_unsafe_queries() -> None:
    initialize_database()

    with pytest.raises(ValueError, match="symbol"):
        read_tick_page(symbol=" ", start_at=BASE_TIME, end_at=BASE_TIME)
    with pytest.raises(ValueError, match="end_at"):
        read_tick_page(symbol="GOLD", start_at=BASE_TIME, end_at=BASE_TIME)
    with pytest.raises(ValueError, match="page_size"):
        read_tick_page(
            symbol="GOLD",
            start_at=BASE_TIME,
            end_at=BASE_TIME + timedelta(seconds=1),
            page_size=1001,
        )
    with pytest.raises(ValueError, match="timezone"):
        read_tick_page(
            symbol="GOLD",
            start_at=datetime(2026, 8, 3, 8, 0),
            end_at=BASE_TIME + timedelta(seconds=1),
        )


def test_replay_does_not_change_raw_tick_rows() -> None:
    initialize_database()
    insert_tick("GOLD:1", BASE_TIME)
    insert_tick("GOLD:2", BASE_TIME + timedelta(milliseconds=1))

    with get_connection() as connection:
        before = connection.execute(
            """
            SELECT event_id, raw_event_json
            FROM tick_events
            ORDER BY event_id;
            """
        ).fetchall()

    read_tick_page(
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(seconds=1),
    )

    with get_connection() as connection:
        after = connection.execute(
            """
            SELECT event_id, raw_event_json
            FROM tick_events
            ORDER BY event_id;
            """
        ).fetchall()

    assert [tuple(row) for row in after] == [tuple(row) for row in before]
