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
                event_id, event_type, event_timestamp, received_at, source,
                event_version, symbol, bid, ask, last, volume, flags,
                source_time_msc, module_version, raw_event_json
            )
            VALUES (?, 'TICK_RECEIVED', ?, ?, 'esas.mt5.bridge', '1.0',
                    'GOLD', ?, ?, ?, ?, ?, ?, ?, '{}');
            """,
            rows,
        )


def row(number: int, seconds: float, source_time: int, *, module: str = "1.6.0", bid: float = 4100.0) -> tuple[object, ...]:
    timestamp = (BASE_TIME + timedelta(seconds=seconds)).isoformat(timespec="microseconds")
    return (
        f"GOLD:{number:04d}",
        timestamp, timestamp,
        bid, bid + 0.5, bid + 0.25, 1, 6,
        int(BASE_TIME.timestamp() * 1000) + source_time, module,
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


def test_remaining_contract_rules_and_boundaries(isolated_database: Path) -> None:
    rows = [
        row(1, 0, 2_000),
        row(2, 1, 3_001),
        row(3, 2, 32_001, bid=-1.0),
    ]
    seed(isolated_database, rows)
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE tick_events
            SET bid = 4101.0, ask = 4100.0,
                received_at = ?
            WHERE event_id = 'GOLD:0002';
            """,
            ((BASE_TIME + timedelta(seconds=8)).isoformat(timespec="microseconds"),),
        )
        connection.execute(
            """
            UPDATE tick_events
            SET event_type = 'PRICE_UPDATED', received_at = ?
            WHERE event_id = 'GOLD:0003';
            """,
            ((BASE_TIME + timedelta(seconds=63)).isoformat(timespec="microseconds"),),
        )
    findings = finding_map(analyze())
    assert findings[("DQ-003", "critical")].count == 1
    assert findings[("DQ-005", "critical")].count == 1
    assert findings[("DQ-007", "critical")].count == 1
    assert findings[("DQ-008", "critical")].count == 1
    assert findings[("DQ-009", "info")].count == 1
    assert findings[("DQ-009", "warning")].count == 1


def test_zero_price_pairs_are_not_negative_spread(isolated_database: Path) -> None:
    seed(isolated_database, [row(1, 0, 0), row(2, 1, 1)])
    with get_connection() as connection:
        connection.execute("UPDATE tick_events SET bid = 0, ask = 1 WHERE event_id = 'GOLD:0001';")
        connection.execute("UPDATE tick_events SET bid = 0, ask = 0 WHERE event_id = 'GOLD:0002';")
    result = analyze()
    findings = finding_map(result)
    assert ("DQ-005", "critical") not in findings
    assert sum(item.count for item in result.findings if item.rule_id == "DQ-006") == 2


def test_time_difference_and_latency_exact_boundaries(isolated_database: Path) -> None:
    seed(isolated_database, [row(1, 0, 2_000), row(2, 1, 31_000)])
    with get_connection() as connection:
        connection.execute(
            "UPDATE tick_events SET received_at = ? WHERE event_id = 'GOLD:0001';",
            ((BASE_TIME + timedelta(seconds=5)).isoformat(timespec="microseconds"),),
        )
        connection.execute(
            "UPDATE tick_events SET received_at = ? WHERE event_id = 'GOLD:0002';",
            ((BASE_TIME - timedelta(seconds=1)).isoformat(timespec="microseconds"),),
        )
    result = analyze()
    clock_findings = [item for item in result.findings if item.rule_id == "DQ-003"]
    assert len(clock_findings) == 1
    assert clock_findings[0].severity == "warning"
    assert clock_findings[0].sample_event_ids == ("GOLD:0002",)
    latency = [item for item in result.findings if item.rule_id == "DQ-009"]
    assert len(latency) == 1
    assert latency[0].reason == "received_at preceded event_timestamp"
