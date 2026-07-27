from backend.app.database.connection import get_connection
from backend.app.models.tick_event import TickReceivedEvent


def save_tick_event(event: TickReceivedEvent) -> bool:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO tick_events
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                event.event_id,
                event.event_type,
                event.timestamp.isoformat(),
                event.source,
                event.version,
                event.symbol,
                event.payload.bid,
                event.payload.ask,
                event.payload.last,
                event.payload.volume,
                event.payload.flags,
                event.payload.source_time_msc,
                event.metadata.module_version,
                event.model_dump_json(),
            ),
        )

        return cursor.rowcount == 1