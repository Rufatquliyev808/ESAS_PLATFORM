from backend.app.database.connection import get_connection


def acknowledge_loss(
    *,
    source: str,
    symbol: str,
    rejected_events: int,
    acknowledged_by: str,
) -> dict[str, object]:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO loss_acknowledgements
            (
                source,
                symbol,
                rejected_events,
                acknowledged_by
            )
            VALUES (?, ?, ?, ?);
            """,
            (source, symbol, rejected_events, acknowledged_by),
        )
        row = connection.execute(
            """
            SELECT
                acknowledgement_id,
                source,
                symbol,
                rejected_events,
                acknowledged_by,
                acknowledged_at
            FROM loss_acknowledgements
            WHERE acknowledgement_id = ?;
            """,
            (cursor.lastrowid,),
        ).fetchone()

    if row is None:
        raise RuntimeError("Loss acknowledgement was not stored")
    return dict(row)


def get_latest_loss_acknowledgement(
    *,
    source: str,
    symbol: str,
) -> dict[str, object] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                acknowledgement_id,
                source,
                symbol,
                rejected_events,
                acknowledged_by,
                acknowledged_at
            FROM loss_acknowledgements
            WHERE source = ? AND symbol = ?
            ORDER BY rejected_events DESC, acknowledgement_id DESC
            LIMIT 1;
            """,
            (source, symbol),
        ).fetchone()

    return None if row is None else dict(row)
