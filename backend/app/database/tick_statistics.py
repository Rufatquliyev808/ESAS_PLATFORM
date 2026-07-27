from typing import Any

from backend.app.database.connection import get_connection


def get_tick_statistics() -> dict[str, Any]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_ticks,
                COUNT(DISTINCT event_id) AS unique_event_ids,
                COUNT(*) - COUNT(DISTINCT event_id) AS duplicate_rows,
                COUNT(DISTINCT symbol) AS symbol_count,
                MIN(event_timestamp) AS first_tick,
                MAX(event_timestamp) AS last_tick,
                MAX(received_at) AS last_received_at
            FROM tick_events;
            """
        ).fetchone()

    return {
        "total_ticks": row["total_ticks"],
        "unique_event_ids": row["unique_event_ids"],
        "duplicate_rows": row["duplicate_rows"],
        "symbol_count": row["symbol_count"],
        "first_tick": row["first_tick"],
        "last_tick": row["last_tick"],
        "last_received_at": row["last_received_at"],
    }