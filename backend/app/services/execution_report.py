from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import MediaObject, ReportArtifact, RunReport

settings = get_settings()


def build_report_summary(
    *,
    status: str,
    total_case_count: int,
    passed_count: int,
    failed_count: int,
    error_count: int,
    cancelled_count: int,
    started_at,
    finished_at,
    failure_code: str | None,
    failure_summary: str | None,
    artifact_totals: dict[str, int] | None = None,
) -> dict[str, Any]:
    artifacts_by_type = artifact_totals or {}
    duration_ms = None
    if started_at is not None and finished_at is not None:
        duration_ms = max(1, int((finished_at - started_at).total_seconds() * 1000))

    return {
        "status": status,
        "counts": {
            "total": total_case_count,
            "passed": passed_count,
            "failed": failed_count,
            "error": error_count,
            "cancelled": cancelled_count,
        },
        "failure": None
        if failure_code is None and failure_summary is None
        else {
            "code": failure_code,
            "summary": failure_summary,
        },
        "timing": {
            "started_at": started_at.isoformat() if started_at is not None else None,
            "finished_at": finished_at.isoformat() if finished_at is not None else None,
            "duration_ms": duration_ms,
        },
        "artifacts": {
            "total": sum(artifacts_by_type.values()),
            "by_type": artifacts_by_type,
        },
        "total_case_count": total_case_count,
        "passed_case_count": passed_count,
        "failed_case_count": failed_count,
        "error_case_count": error_count,
        "cancelled_case_count": cancelled_count,
        "message": failure_summary,
    }


def create_report_artifact(
    db: Session,
    *,
    report: RunReport,
    media: MediaObject,
    artifact_type: str,
    case_run_id: int | None = None,
    step_result_id: int | None = None,
) -> ReportArtifact:
    artifact = ReportArtifact(
        report_id=report.id,
        artifact_type=artifact_type,
        media_object_id=media.id,
        case_run_id=case_run_id,
        step_result_id=step_result_id,
        artifact_url=_media_content_url(media.id),
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


def refresh_report_artifact_summary(db: Session, report: RunReport) -> None:
    artifact_rows = db.scalars(
        select(ReportArtifact).where(ReportArtifact.report_id == report.id)
    ).all()
    by_type: dict[str, int] = {}
    for artifact in artifact_rows:
        by_type[artifact.artifact_type] = by_type.get(artifact.artifact_type, 0) + 1
    summary_json = dict(report.summary_json or {})
    summary_json["artifacts"] = {
        "total": len(artifact_rows),
        "by_type": by_type,
    }
    report.summary_json = summary_json
    db.commit()
    db.refresh(report)


def media_content_url(media_object_id: int) -> str:
    return _media_content_url(media_object_id)


def _media_content_url(media_object_id: int) -> str:
    return f"{settings.api_v1_prefix}/media-objects/{media_object_id}/content"
