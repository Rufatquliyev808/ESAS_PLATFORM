from dataclasses import dataclass
from collections.abc import Iterator
from datetime import UTC, datetime
import sqlite3

from backend.app.database.connection import get_database_path


MIN_PAGE_SIZE = 1
MAX_PAGE_SIZE = 1000


@dataclass(frozen=True)
class TickPosition:
    event_timestamp: datetime
    event_id: str


@dataclass(frozen=True)
class ReplayTick:
    event_id: str
    event_type: str
    event_timestamp: str
    received_at: str
    symbol: str
    bid: float
    ask: float
    last: float
    volume: int
    flags: int
    source_time_msc: int
    source: str
    event_version: str
    module_version: str


@dataclass(frozen=True)
class ReplayTickPage:
    items: tuple[ReplayTick, ...]
    has_more: bool
    next_position: TickPosition | None


def _utc_text(value: datetime, field_name: str) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")

    return value.astimezone(UTC).isoformat(timespec="microseconds")


def _read_only_connection() -> sqlite3.Connection:
    database_path = get_database_path()
    connection = sqlite3.connect(
        f"{database_path.resolve().as_uri()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON;")
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA busy_timeout = 5000;")
    return connection


def read_tick_page(
    *,
    symbol: str,
    start_at: datetime,
    end_at: datetime,
    page_size: int = 250,
    after: TickPosition | None = None,
    through: TickPosition | None = None,
) -> ReplayTickPage:
    normalized_symbol = symbol.strip()
    if not normalized_symbol:
        raise ValueError("symbol must not be empty")
    if not MIN_PAGE_SIZE <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(
            f"page_size must be between {MIN_PAGE_SIZE} and {MAX_PAGE_SIZE}"
        )

    start_text = _utc_text(start_at, "start_at")
    end_text = _utc_text(end_at, "end_at")
    if end_text <= start_text:
        raise ValueError("end_at must be later than start_at")

    parameters: list[object] = [normalized_symbol, start_text, end_text]
    boundary_sql = ""
    if through is not None:
        through_timestamp = _utc_text(
            through.event_timestamp,
            "through.event_timestamp",
        )
        if not through.event_id:
            raise ValueError("through.event_id must not be empty")
        boundary_sql = """
            AND (
                event_timestamp < ?
                OR (event_timestamp = ? AND event_id <= ?)
            )
        """
        parameters.extend(
            [through_timestamp, through_timestamp, through.event_id]
        )
    continuation_sql = ""
    if after is not None:
        after_timestamp = _utc_text(
            after.event_timestamp,
            "after.event_timestamp",
        )
        if not after.event_id:
            raise ValueError("after.event_id must not be empty")
        if after_timestamp < start_text or after_timestamp >= end_text:
            raise ValueError("after position is outside the requested interval")

        continuation_sql = """
            AND (
                event_timestamp > ?
                OR (event_timestamp = ? AND event_id > ?)
            )
        """
        parameters.extend(
            [after_timestamp, after_timestamp, after.event_id]
        )

    parameters.append(page_size + 1)
    with _read_only_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT
                event_id,
                event_type,
                event_timestamp,
                received_at,
                symbol,
                bid,
                ask,
                last,
                volume,
                flags,
                source_time_msc,
                source,
                event_version,
                module_version
            FROM tick_events
            WHERE symbol = ?
              AND event_timestamp >= ?
              AND event_timestamp < ?
              {boundary_sql}
              {continuation_sql}
            ORDER BY event_timestamp ASC, event_id ASC
            LIMIT ?;
            """,
            parameters,
        ).fetchall()

    has_more = len(rows) > page_size
    page_rows = rows[:page_size]
    items = tuple(ReplayTick(**dict(row)) for row in page_rows)
    next_position = None
    if has_more and items:
        last_item = items[-1]
        next_position = TickPosition(
            event_timestamp=datetime.fromisoformat(last_item.event_timestamp),
            event_id=last_item.event_id,
        )

    return ReplayTickPage(
        items=items,
        has_more=has_more,
        next_position=next_position,
    )


def iter_tick_identity_batches(
    *,
    symbol: str,
    start_at: datetime,
    end_at: datetime,
    batch_size: int = 1000,
) -> Iterator[tuple[TickPosition, ...]]:
    normalized_symbol = symbol.strip()
    if not normalized_symbol:
        raise ValueError("symbol must not be empty")
    if not MIN_PAGE_SIZE <= batch_size <= MAX_PAGE_SIZE:
        raise ValueError(
            f"batch_size must be between {MIN_PAGE_SIZE} and {MAX_PAGE_SIZE}"
        )

    start_text = _utc_text(start_at, "start_at")
    end_text = _utc_text(end_at, "end_at")
    if end_text <= start_text:
        raise ValueError("end_at must be later than start_at")

    with _read_only_connection() as connection:
        connection.execute("BEGIN;")
        cursor = connection.execute(
            """
            SELECT event_timestamp, event_id
            FROM tick_events
            WHERE symbol = ?
              AND event_timestamp >= ?
              AND event_timestamp < ?
            ORDER BY event_timestamp ASC, event_id ASC;
            """,
            (normalized_symbol, start_text, end_text),
        )
        while rows := cursor.fetchmany(batch_size):
            yield tuple(
                TickPosition(
                    event_timestamp=datetime.fromisoformat(
                        row["event_timestamp"]
                    ),
                    event_id=row["event_id"],
                )
                for row in rows
            )


def iter_tick_batches(
    *,
    symbol: str,
    start_at: datetime,
    end_at: datetime,
    batch_size: int = 1000,
) -> Iterator[tuple[ReplayTick, ...]]:
    normalized_symbol = symbol.strip()
    if not normalized_symbol:
        raise ValueError("symbol must not be empty")
    if not MIN_PAGE_SIZE <= batch_size <= MAX_PAGE_SIZE:
        raise ValueError(
            f"batch_size must be between {MIN_PAGE_SIZE} and {MAX_PAGE_SIZE}"
        )

    start_text = _utc_text(start_at, "start_at")
    end_text = _utc_text(end_at, "end_at")
    if end_text <= start_text:
        raise ValueError("end_at must be later than start_at")

    with _read_only_connection() as connection:
        connection.execute("BEGIN;")
        cursor = connection.execute(
            """
            SELECT
                event_id, event_type, event_timestamp, received_at, symbol, bid, ask,
                last, volume, flags, source_time_msc, source,
                event_version, module_version
            FROM tick_events
            WHERE symbol = ?
              AND event_timestamp >= ?
              AND event_timestamp < ?
            ORDER BY event_timestamp ASC, event_id ASC;
            """,
            (normalized_symbol, start_text, end_text),
        )
        while rows := cursor.fetchmany(batch_size):
            yield tuple(ReplayTick(**dict(row)) for row in rows)
