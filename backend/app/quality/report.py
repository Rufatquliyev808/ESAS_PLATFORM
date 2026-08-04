from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json

from backend.app.replay.result_manifest import (
    ReplayResultManifest,
    create_replay_result_manifest,
)
from backend.app.quality.tick_quality import (
    QualityFinding,
    analyze_tick_quality,
)
from backend.app.quality.statistics import (
    TickQualityStatistics,
    calculate_tick_quality_statistics,
)


QUALITY_REPORT_VERSION = "1.0"


@dataclass(frozen=True)
class QualitySummary:
    status: str
    tick_count: int
    critical_count: int
    warning_count: int
    info_count: int


@dataclass(frozen=True)
class ReplayQualityReport:
    report_id: str
    report_version: str
    session_id: str
    replay_manifest: ReplayResultManifest
    summary: QualitySummary
    findings: tuple[QualityFinding, ...]
    statistics: TickQualityStatistics
    content_fingerprint: str


def _summary(tick_count: int, findings: tuple[QualityFinding, ...]) -> QualitySummary:
    counts = {
        severity: sum(item.count for item in findings if item.severity == severity)
        for severity in ("critical", "warning", "info")
    }
    status = "fail" if counts["critical"] else "review" if counts["warning"] else "pass"
    return QualitySummary(
        status=status,
        tick_count=tick_count,
        critical_count=counts["critical"],
        warning_count=counts["warning"],
        info_count=counts["info"],
    )


def create_replay_quality_report(
    *,
    session_id: str,
    batch_size: int = 1000,
) -> ReplayQualityReport:
    manifest = create_replay_result_manifest(
        session_id=session_id,
        batch_size=batch_size,
    )
    quality = analyze_tick_quality(
        symbol=manifest.symbol,
        start_at=datetime.fromisoformat(manifest.start_at),
        end_at=datetime.fromisoformat(manifest.end_at),
        batch_size=batch_size,
    )
    if quality.tick_count != manifest.result_tick_count:
        raise RuntimeError("quality report tick count does not match replay manifest")
    summary = _summary(quality.tick_count, quality.findings)
    statistics = calculate_tick_quality_statistics(
        symbol=manifest.symbol,
        start_at=datetime.fromisoformat(manifest.start_at),
        end_at=datetime.fromisoformat(manifest.end_at),
        batch_size=batch_size,
    )
    if statistics.tick_count != quality.tick_count:
        raise RuntimeError("quality statistics tick count does not match findings")
    content = {
        "report_version": QUALITY_REPORT_VERSION,
        "replay_contract_version": manifest.replay_contract_version,
        "quality_rule_version": manifest.quality_rule_version,
        "symbol": manifest.symbol,
        "start_at": manifest.start_at,
        "end_at": manifest.end_at,
        "dataset_fingerprint": manifest.dataset_fingerprint,
        "result_fingerprint": manifest.result_fingerprint,
        "summary": asdict(summary),
        "findings": [asdict(item) for item in quality.findings],
        "statistics": asdict(statistics),
    }
    encoded = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    fingerprint = f"sha256:{sha256(encoded).hexdigest()}"
    return ReplayQualityReport(
        report_id="dqr_" + fingerprint.removeprefix("sha256:")[:24],
        report_version=QUALITY_REPORT_VERSION,
        session_id=session_id,
        replay_manifest=manifest,
        summary=summary,
        findings=quality.findings,
        statistics=statistics,
        content_fingerprint=fingerprint,
    )
