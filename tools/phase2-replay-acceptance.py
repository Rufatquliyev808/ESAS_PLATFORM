from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from backend.app.database.connection import get_connection
from backend.app.database.replay_command_repository import execute_replay_command
from backend.app.database.replay_session_repository import (
    create_replay_session,
    get_replay_session,
    run_max_speed_replay,
)
from backend.app.quality.report import create_replay_quality_report
from backend.app.replay.result_manifest import (
    create_replay_result_manifest,
    prove_replay_reproduction,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a sanitized Phase 2 replay acceptance proof."
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start-at")
    parser.add_argument("--end-at")
    parser.add_argument("--latest-minutes", type=int)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Required acknowledgement before writing replay metadata.",
    )
    return parser.parse_args()


def run_step(session_id: str, actor: str) -> None:
    session = get_replay_session(session_id)
    execute_replay_command(
        session_id=session_id,
        actor=actor,
        actor_role="acceptance",
        idempotency_key=f"accept-start-{uuid4()}",
        command="start",
        expected_state_version=session.state_version,
    )
    while True:
        session = get_replay_session(session_id)
        if session.state == "completed":
            return
        execute_replay_command(
            session_id=session_id,
            actor=actor,
            actor_role="acceptance",
            idempotency_key=f"accept-step-{uuid4()}",
            command="step",
            expected_state_version=session.state_version,
            requested_ticks=1000,
        )


def run_max_speed(session_id: str, actor: str) -> None:
    session = get_replay_session(session_id)
    execute_replay_command(
        session_id=session_id,
        actor=actor,
        actor_role="acceptance",
        idempotency_key=f"accept-start-{uuid4()}",
        command="start",
        expected_state_version=session.state_version,
    )
    run_max_speed_replay(
        session_id=session_id,
        actor="PHASE2-ACCEPTANCE-WORKER",
        actor_role="worker",
    )


def main() -> int:
    args = parse_args()
    if not args.allow_production:
        raise SystemExit("Refusing to write replay metadata without --allow-production")
    if args.latest_minutes is not None:
        if args.latest_minutes < 1 or args.start_at or args.end_at:
            raise SystemExit("--latest-minutes must be positive and used without explicit interval")
        with get_connection() as connection:
            latest = connection.execute(
                "SELECT MAX(event_timestamp) FROM tick_events WHERE symbol = ?",
                (args.symbol.strip().upper(),),
            ).fetchone()[0]
        if latest is None:
            raise SystemExit("No ticks exist for the requested symbol")
        end_at = datetime.fromisoformat(latest) + timedelta(microseconds=1)
        start_at = end_at - timedelta(minutes=args.latest_minutes)
    elif args.start_at and args.end_at:
        start_at = datetime.fromisoformat(args.start_at)
        end_at = datetime.fromisoformat(args.end_at)
    else:
        raise SystemExit("Use --latest-minutes or both --start-at and --end-at")
    if start_at.tzinfo is None or end_at.tzinfo is None or end_at <= start_at:
        raise SystemExit("A valid timezone-aware [start-at, end-at) interval is required")

    with get_connection() as connection:
        raw_before = connection.execute("SELECT COUNT(*) FROM tick_events").fetchone()[0]

    sessions = []
    for mode in ("step", "step", "max_speed", "max_speed"):
        session = create_replay_session(
            created_by=args.actor,
            actor_role="acceptance",
            symbol=args.symbol.strip().upper(),
            start_at=start_at,
            end_at=end_at,
            mode=mode,
        )
        if session.state != "completed":
            (run_step if mode == "step" else run_max_speed)(session.session_id, args.actor)
        sessions.append(get_replay_session(session.session_id))

    manifests = [create_replay_result_manifest(session_id=item.session_id) for item in sessions]
    step_proof = prove_replay_reproduction(manifests[0], manifests[1])
    max_proof = prove_replay_reproduction(manifests[2], manifests[3])
    cross_mode_equal = (
        manifests[0].dataset_fingerprint == manifests[2].dataset_fingerprint
        and manifests[0].result_fingerprint == manifests[2].result_fingerprint
        and manifests[0].result_tick_count == manifests[2].result_tick_count
    )
    reports = [create_replay_quality_report(session_id=item.session_id) for item in sessions]

    with get_connection() as connection:
        raw_after = connection.execute("SELECT COUNT(*) FROM tick_events").fetchone()[0]

    passed = (
        raw_before == raw_after
        and cross_mode_equal
        and all(item.state == "completed" for item in sessions)
        and all(report.summary.status != "fail" for report in reports)
    )
    evidence = {
        "evidence_contract": "phase2-replay-acceptance-v1",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "result": "passed" if passed else "failed",
        "scope": {"symbol": args.symbol.strip().upper(), "start_at": start_at.isoformat(), "end_at": end_at.isoformat()},
        "integrity": {"raw_tick_count_before": raw_before, "raw_tick_count_after": raw_after, "unchanged": raw_before == raw_after},
        "sessions": [asdict(item) for item in sessions],
        "manifests": [asdict(item) for item in manifests],
        "reproduction": {"step": asdict(step_proof), "max_speed": asdict(max_proof), "cross_mode_equal": cross_mode_equal},
        "quality": [asdict(report) for report in reports],
        "contains_raw_tick_payload": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Phase 2 replay acceptance: {evidence['result'].upper()}")
    print(f"Evidence: {args.output}")
    print(f"Ticks: {manifests[0].result_tick_count}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
