from __future__ import annotations

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import (
    BaselineRevision,
    DeviceProfile,
    EnvironmentProfile,
    MediaObject,
    ReportArtifact,
    RunReport,
    StepResult,
    Template,
    TemplateMaskRegion,
    TestCaseRun,
    TestRun,
    User,
    utc_now,
)
from app.services import assets as asset_service
from app.services.execution import (
    build_execution_steps,
    create_report_artifact,
    finalize_cancelled_test_run,
    finalize_completed_test_run,
    finalize_errored_test_run,
    get_report_by_test_run,
)
from app.workers.browser import build_browser_execution_adapter
from app.workers.vision import MaskRegionRatio, TemplateAssertionContext

settings = get_settings()


def process_test_run(test_run_id: int) -> None:
    with SessionLocal() as db:
        test_run = db.get(TestRun, test_run_id)
        if test_run is None:
            return
        if test_run.status == "cancelling":
            latest = finalize_cancelled_test_run(db, test_run)
            _persist_report_artifacts(db, latest.id, [])
            return
        if test_run.status != "queued":
            return

        started_at = utc_now()
        test_run.status = "running"
        test_run.started_at = started_at
        db.commit()

        environment_profile = db.get(EnvironmentProfile, test_run.environment_profile_id)
        device_profile = db.get(DeviceProfile, test_run.device_profile_id) if test_run.device_profile_id is not None else None
        triggered_user = db.get(User, test_run.triggered_by) if test_run.triggered_by is not None else None
        captured_media: list[MediaObject] = []

        try:
            browser_adapter = build_browser_execution_adapter()

            case_runs = db.scalars(
                select(TestCaseRun).where(TestCaseRun.test_run_id == test_run_id).order_by(TestCaseRun.sort_order.asc())
            ).all()

            passed_count = 0
            failed_count = 0
            error_count = 0

            for case_run in case_runs:
                db.refresh(test_run)
                if test_run.status == "cancelling":
                    latest = finalize_cancelled_test_run(db, test_run)
                    _persist_report_artifacts(db, latest.id, captured_media)
                    return

                case_started_at = utc_now()
                case_run.status = "running"
                case_run.started_at = case_started_at
                db.commit()

                steps = build_execution_steps(
                    db,
                    workspace_id=test_run.workspace_id,
                    test_case_id=case_run.test_case_id,
                )
                template_contexts = _build_template_contexts(db, workspace_id=test_run.workspace_id, steps=steps)

                for _ in steps:
                    db.refresh(test_run)
                    if test_run.status == "cancelling":
                        latest = finalize_cancelled_test_run(db, test_run)
                        _persist_report_artifacts(db, latest.id, captured_media)
                        return

                execution_result = browser_adapter.execute_case(
                    base_url=environment_profile.base_url if environment_profile is not None else "about:blank",
                    case_run_id=case_run.id,
                    device_profile=device_profile,
                    steps=steps,
                    template_contexts=template_contexts,
                )

                persisted_step_results: list[StepResult] = []
                for step_result in execution_result.step_results:
                    persisted = StepResult(
                        case_run_id=case_run.id,
                        step_no=step_result.step_no,
                        step_type=step_result.step_type,
                        status=step_result.status,
                        score_value=step_result.score_value,
                        error_message=step_result.error_message,
                        started_at=step_result.started_at,
                        finished_at=step_result.finished_at,
                        duration_ms=step_result.duration_ms,
                        expected_media_object_id=step_result.expected_media_object_id,
                    )
                    db.add(persisted)
                    db.flush()
                    if step_result.actual_artifact is not None:
                        actual_media = asset_service.create_media_object_from_bytes(
                            db,
                            user=triggered_user,
                            workspace_id=test_run.workspace_id,
                            file_bytes=step_result.actual_artifact.content_bytes,
                            file_name=step_result.actual_artifact.file_name,
                            mime_type=step_result.actual_artifact.content_type,
                            usage="artifact",
                            remark=f"case-run-{case_run.id}-step-{step_result.step_no}-{step_result.actual_artifact.artifact_type}",
                        )
                        persisted.actual_media_object_id = actual_media.id
                        captured_media.append(actual_media)
                    if step_result.diff_artifact is not None:
                        diff_media = asset_service.create_media_object_from_bytes(
                            db,
                            user=triggered_user,
                            workspace_id=test_run.workspace_id,
                            file_bytes=step_result.diff_artifact.content_bytes,
                            file_name=step_result.diff_artifact.file_name,
                            mime_type=step_result.diff_artifact.content_type,
                            usage="artifact",
                            remark=f"case-run-{case_run.id}-step-{step_result.step_no}-{step_result.diff_artifact.artifact_type}",
                        )
                        persisted.diff_media_object_id = diff_media.id
                        captured_media.append(diff_media)
                    persisted_step_results.append(persisted)

                if execution_result.artifact is not None:
                    media = asset_service.create_media_object_from_bytes(
                        db,
                        user=triggered_user,
                        workspace_id=test_run.workspace_id,
                        file_bytes=execution_result.artifact.content_bytes,
                        file_name=execution_result.artifact.file_name,
                        mime_type=execution_result.artifact.content_type,
                        usage="artifact",
                        remark=f"case-run-{case_run.id}-screenshot",
                    )
                    captured_media.append(media)
                    if persisted_step_results and persisted_step_results[-1].actual_media_object_id is None:
                        persisted_step_results[-1].actual_media_object_id = media.id

                case_run.status = execution_result.status
                case_run.finished_at = utc_now()
                case_run.duration_ms = max(1, int((case_run.finished_at - case_started_at).total_seconds() * 1000))
                case_run.failure_reason_code = execution_result.failure_reason_code
                case_run.failure_summary = execution_result.failure_summary

                if execution_result.status == "passed":
                    passed_count += 1
                elif execution_result.status == "failed":
                    failed_count += 1
                else:
                    error_count += 1
                db.commit()

            if test_run.total_case_count <= 0:
                test_run.finished_at = utc_now()
                test_run.status = "error"
                db.add(
                    RunReport(
                        test_run_id=test_run.id,
                        summary_status="error",
                        summary_json={
                            "total_case_count": 0,
                            "passed_case_count": 0,
                            "failed_case_count": 0,
                            "error_case_count": 0,
                            "message": "Test run contains no executable cases.",
                        },
                        generated_at=utc_now(),
                    )
                )
                db.commit()
                return

            latest_test_run = finalize_completed_test_run(
                db,
                test_run,
                passed_count=passed_count,
                failed_count=failed_count,
                error_count=error_count,
            )
            _persist_report_artifacts(db, latest_test_run.id, captured_media)
        except Exception as exc:  # noqa: BLE001
            latest = finalize_errored_test_run(
                db,
                test_run,
                error_message=f"{type(exc).__name__}: {str(exc).strip() or 'unexpected execution error'}",
            )
            _persist_report_artifacts(db, latest.id, captured_media)


def _persist_report_artifacts(db, test_run_id: int, media_objects: list[MediaObject]) -> None:
    if not media_objects:
        return
    report = get_report_by_test_run(db, test_run_id)
    if report is None:
        return
    existing_media_ids = {
        artifact.media_object_id
        for artifact in db.scalars(select(ReportArtifact).where(ReportArtifact.report_id == report.id)).all()
    }
    for media in media_objects:
        if media.id in existing_media_ids:
            continue
        create_report_artifact(db, report=report, media=media)
        existing_media_ids.add(media.id)


def _build_template_contexts(db, *, workspace_id: int, steps) -> dict[int, TemplateAssertionContext]:
    template_ids = {
        step.template_id
        for step in steps
        if step.template_id is not None and step.step_type in {"template_assert", "ocr_assert"}
    }
    contexts: dict[int, TemplateAssertionContext] = {}
    for template_id in template_ids:
        template = db.get(Template, template_id)
        if template is None or template.workspace_id != workspace_id or template.is_deleted:
            continue
        if template.current_baseline_revision_id is None:
            continue
        baseline = db.get(BaselineRevision, template.current_baseline_revision_id)
        if baseline is None:
            continue
        media = db.get(MediaObject, baseline.media_object_id)
        if media is None:
            continue
        mask_regions = db.scalars(
            select(TemplateMaskRegion)
            .where(TemplateMaskRegion.template_id == template.id)
            .order_by(TemplateMaskRegion.sort_order.asc())
        ).all()
        contexts[template_id] = TemplateAssertionContext(
            template_id=template.id,
            template_name=template.template_name,
            match_strategy=template.match_strategy,
            threshold_value=float(template.threshold_value),
            baseline_media_object_id=media.id,
            baseline_file_path=settings.local_storage_path / media.object_key,
            mask_regions=[
                MaskRegionRatio(
                    x_ratio=float(region.x_ratio),
                    y_ratio=float(region.y_ratio),
                    width_ratio=float(region.width_ratio),
                    height_ratio=float(region.height_ratio),
                )
                for region in mask_regions
            ],
        )
    return contexts
