from typing import Any

from backend.app.database.connection import get_connection


def get_tick_statistics() -> dict[str, Any]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_ticks,
                COUNT(DISTINCT symbol) AS symbol_count,
                MIN(event_timestamp) AS first_tick,
                MAX(event_timestamp) AS last_tick,
                MAX(received_at) AS last_received_at
            FROM tick_events;
            """
        ).fetchone()

    return {
        "total_ticks": row["total_ticks"],
        # event_id is the table's primary key, so every stored event is unique.
        "unique_event_ids": row["total_ticks"],
        "duplicate_rows": 0,
        "symbol_count": row["symbol_count"],
        "first_tick": row["first_tick"],
        "last_tick": row["last_tick"],
        "last_received_at": row["last_received_at"],
    }
