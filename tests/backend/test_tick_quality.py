from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.quality.tick_quality import analyze_tick_quality


BASE_TIME = datetime(2026, 8, 4, 20, 0, tzinfo=UTC)


def seed(database_path: Path, rows: list[tuple[object, ...]]) -> None:
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
                    'GOLD', ?, ?, ?, ?, ?, ?, ?, '{}');
            """,
            rows,
        )


def row(number: int, seconds: float, source_time: int, *, module: str = "1.6.0", bid: float = 4100.0) -> tuple[object, ...]:
    return (
        f"GOLD:{number:04d}",
        (BASE_TIME + timedelta(seconds=seconds)).isoformat(timespec="microseconds"),
        bid, bid + 0.5, bid + 0.25, 1, 6, source_time, module,
    )


def finding_map(result: object) -> dict[tuple[str, str], object]:
    return {(item.rule_id, item.severity): item for item in result.findings}


def analyze(**extra: object):
    return analyze_tick_quality(
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(hours=1),
        **extra,
    )


def test_gap_thresholds_and_exact_boundary(isolated_database: Path) -> None:
    seed(isolated_database, [row(1, 0, 1), row(2, 30, 2), row(3, 61, 3), row(4, 362, 4)])
    findings = finding_map(analyze())
    assert findings[("DQ-004", "info")].sample_event_ids == ("GOLD:0003",)
    assert findings[("DQ-004", "warning")].sample_event_ids == ("GOLD:0004",)


def test_source_time_backwards_resets_for_module_segment(isolated_database: Path) -> None:
    seed(isolated_database, [row(1, 0, 100), row(2, 1, 99), row(3, 2, 1, module="1.7.0"), row(4, 3, 2, module="1.7.0")])
    findings = finding_map(analyze())
    assert findings[("DQ-002", "warning")].count == 1
    assert findings[("DQ-002", "warning")].first_event_id == "GOLD:0002"


def test_same_timestamp_is_legal_and_payload_duplicate_is_separate(isolated_database: Path) -> None:
    seed(isolated_database, [row(1, 0, 100), row(2, 0, 101), row(3, 1, 101)])
    findings = finding_map(analyze())
    assert ("DQ-004", "info") not in findings
    assert findings[("DQ-011", "info")].sample_event_ids == ("GOLD:0003",)


def test_findings_are_batch_independent_and_stable(isolated_database: Path) -> None:
    seed(isolated_database, [row(1, 0, 100), row(2, 31, 99), row(3, 32, 99)])
    first = analyze(batch_size=1)
    second = analyze(batch_size=3)
    assert first == second
    assert all(item.finding_id.startswith("dqf_") for item in first.findings)


def test_analysis_does_not_change_raw_ticks(isolated_database: Path) -> None:
    seed(isolated_database, [row(1, 0, 100), row(2, 31, 99)])
    with get_connection() as connection:
        before = connection.execute("SELECT COUNT(*), SUM(source_time_msc) FROM tick_events;").fetchone()
    analyze(batch_size=1)
    with get_connection() as connection:
        after = connection.execute("SELECT COUNT(*), SUM(source_time_msc) FROM tick_events;").fetchone()
    assert tuple(before) == tuple(after)
