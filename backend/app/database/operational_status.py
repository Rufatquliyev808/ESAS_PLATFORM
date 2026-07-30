from datetime import datetime, timezone

from backend.app.database.connection import get_database_path
from backend.app.database.loss_acknowledgements import (
    get_latest_loss_acknowledgement,
)
from backend.app.database.tick_statistics import get_tick_statistics
from backend.app.operational.bridge_status import get_bridge_statuses


STALE_AFTER_SECONDS = 30


def get_operational_status() -> dict[str, object]:
    statistics = get_tick_statistics()
    bridge_reports = []
    for report in get_bridge_statuses():
        acknowledgement = get_latest_loss_acknowledgement(
            source=str(report["source"]),
            symbol=str(report["symbol"]),
        )
        rejected_events = int(report["rejected_events"])
        acknowledged_events = (
            0
            if acknowledgement is None
            else int(acknowledgement["rejected_events"])
        )
        report["loss_acknowledged"] = (
            rejected_events == 0 or acknowledged_events >= rejected_events
        )
        report["acknowledged_rejected_events"] = acknowledged_events
        report["loss_acknowledged_at"] = (
            None
            if acknowledgement is None
            else acknowledgement["acknowledged_at"]
        )
        report["loss_acknowledged_by"] = (
            None
            if acknowledgement is None
            else acknowledgement["acknowledged_by"]
        )
        bridge_reports.append(report)
    database_path = get_database_path()
    last_received_at = statistics["last_received_at"]

    seconds_since_last_tick: float | None = None
    stream_status = "waiting"

    if last_received_at is not None:
        last_received = datetime.fromisoformat(
            str(last_received_at).replace("Z", "+00:00")
        )

        seconds_since_last_tick = max(
            0.0,
            (datetime.now(timezone.utc) - last_received).total_seconds(),
        )

        stream_status = (
            "active"
            if seconds_since_last_tick <= STALE_AFTER_SECONDS
            else "stale"
        )

    has_bridge_degradation = any(
        int(report["queue_count"]) >= int(report["queue_capacity"])
        or (
            report["queue_status"] == "degraded"
            and report["last_queue_error"] != "queue_full"
        )
        or not bool(report["loss_acknowledged"])
        for report in bridge_reports
    )

    return {
        "status": "degraded" if has_bridge_degradation else "ok",
        "database": {
            "path": str(database_path),
            "exists": database_path.exists(),
        },
        "tick_stream": {
            "status": stream_status,
            "stale_after_seconds": STALE_AFTER_SECONDS,
            "seconds_since_last_tick": seconds_since_last_tick,
            "last_received_at": last_received_at,
            "total_ticks": statistics["total_ticks"],
        },
        "bridge_delivery": {
            "status": (
                "waiting"
                if not bridge_reports
                else (
                    "degraded"
                    if has_bridge_degradation
                    else "healthy"
                )
            ),
            "bridges": bridge_reports,
        },
    }
