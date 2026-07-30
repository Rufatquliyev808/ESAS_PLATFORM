from datetime import datetime, timezone
from threading import Lock

from backend.app.models.bridge_status import BridgeStatusReport


_status_lock = Lock()
_latest_reports: dict[str, dict[str, object]] = {}


def save_bridge_status(report: BridgeStatusReport) -> dict[str, object]:
    key = f"{report.source}:{report.symbol}"
    stored_report: dict[str, object] = {
        **report.model_dump(),
        "reported_at": datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z"),
    }

    with _status_lock:
        _latest_reports[key] = stored_report

    return stored_report.copy()


def get_bridge_statuses() -> list[dict[str, object]]:
    with _status_lock:
        return [
            report.copy()
            for _, report in sorted(_latest_reports.items())
        ]


def get_bridge_status(
    source: str,
    symbol: str,
) -> dict[str, object] | None:
    key = f"{source}:{symbol}"
    with _status_lock:
        report = _latest_reports.get(key)
        return None if report is None else report.copy()
