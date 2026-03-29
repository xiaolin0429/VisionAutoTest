from __future__ import annotations

import argparse
import base64
import re

from sqlalchemy import create_engine, delete, func, select, text, update
from sqlalchemy.engine import URL, make_url

from app.core.config import get_settings
from app.core.security import hash_secret
from app.db.migrations import upgrade_database
from app.db.session import SessionLocal
from app.models import (
    BaselineRevision,
    DeviceProfile,
    EnvironmentProfile,
    SuiteCase,
    Template,
    TestCase,
    TestCaseStep,
    TestSuite,
    User,
    Workspace,
    WorkspaceMember,
)

DATABASE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DEMO_WORKSPACE_CODE = "mvp_demo"
DEMO_WORKSPACE_NAME = "MVP Demo Workspace"
DEMO_WORKSPACE_DESCRIPTION = "Seeded demo workspace for first-start acceptance runs."
DEMO_ENV_PROFILE_NAME = "demo-local"
DEMO_ENV_PROFILE_DESCRIPTION = "Built-in backend acceptance target page."
DEMO_DEVICE_PROFILE_NAME = "desktop-default"
DEMO_TEMPLATE_CODE = "demo_placeholder_template"
DEMO_TEMPLATE_NAME = "Demo Placeholder Template"
DEMO_CASE_CODE = "demo_smoke_case"
DEMO_CASE_NAME = "Demo Smoke Case"
DEMO_SUITE_CODE = "demo_smoke_suite"
DEMO_SUITE_NAME = "Demo Smoke Suite"
DEMO_PLACEHOLDER_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9s2GoswAAAAASUVORK5CYII="
)
DEMO_CASE_STEPS = [
    {"step_no": 1, "step_type": "wait", "step_name": "Wait Demo Page", "payload_json": {"ms": 200}},
    {
        "step_no": 2,
        "step_type": "input",
        "step_name": "Fill Operator Name",
        "payload_json": {"selector": "[data-testid='name-input']", "text": "VisionAutoTest"},
    },
    {
        "step_no": 3,
        "step_type": "click",
        "step_name": "Submit Demo Form",
        "payload_json": {"selector": "[data-testid='submit-button']"},
    },
    {"step_no": 4, "step_type": "wait", "step_name": "Wait Result Banner", "payload_json": {"ms": 150}},
]


def initialize_database(
    *,
    ensure_database: bool = True,
    run_migrations: bool = True,
    seed_admin: bool = True,
    seed_demo_data: bool = True,
) -> None:
    settings = get_settings()
    if ensure_database:
        ensure_application_database()
    if run_migrations and settings.database_auto_migrate:
        upgrade_database(database_url=settings.database_url)
    settings.local_storage_path.mkdir(parents=True, exist_ok=True)
    if seed_admin:
        seed_default_admin()
    if seed_demo_data:
        seed_demo_acceptance_data()


def ensure_application_database() -> None:
    settings = get_settings()
    database_url = make_url(settings.database_url)
    if not should_auto_create_database(database_url):
        return

    admin_database_url = resolve_admin_database_url(database_url)
    database_name = database_url.database
    if database_name is None:
        raise RuntimeError("Application database name is missing from VAT_DATABASE_URL.")
    validate_database_name(database_name)

    admin_engine = create_engine(
        admin_database_url.render_as_string(hide_password=False),
        future=True,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )
    try:
        with admin_engine.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
                {"database_name": database_name},
            )
            if exists:
                return
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    finally:
        admin_engine.dispose()


def seed_default_admin() -> None:
    settings = get_settings()
    if not settings.default_admin_username or not settings.default_admin_password:
        return
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.username == settings.default_admin_username, User.is_deleted.is_(False)))
        if admin is not None:
            return
        db.add(
            User(
                username=settings.default_admin_username,
                display_name="Administrator",
                password_hash=hash_secret(settings.default_admin_password),
                status="active",
            )
        )
        db.commit()


def seed_demo_acceptance_data(*, force: bool = False) -> None:
    settings = get_settings()
    if not force and settings.app_env != "development":
        return
    if not settings.default_admin_username:
        return

    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.username == settings.default_admin_username, User.is_deleted.is_(False)))
        if admin is None:
            return

        workspace = _ensure_demo_workspace(db, admin)
        _ensure_demo_workspace_admin_membership(db, workspace_id=workspace.id, admin=admin)
        _ensure_demo_environment_profile(db, workspace_id=workspace.id, admin=admin)
        _ensure_demo_device_profile(db, workspace_id=workspace.id, admin=admin)
        demo_media = _ensure_demo_placeholder_media(db, workspace_id=workspace.id, admin=admin)
        _ensure_demo_template(db, workspace_id=workspace.id, admin=admin, media_object_id=demo_media.id)
        demo_case = _ensure_demo_test_case(db, workspace_id=workspace.id, admin=admin)
        _replace_demo_case_steps(db, test_case_id=demo_case.id)
        demo_suite = _ensure_demo_test_suite(db, workspace_id=workspace.id, admin=admin)
        _replace_demo_suite_cases(db, test_suite_id=demo_suite.id, test_case_id=demo_case.id)


def _ensure_demo_workspace(db, admin: User) -> Workspace:
    workspace = db.scalar(
        select(Workspace).where(
            Workspace.workspace_code == DEMO_WORKSPACE_CODE,
            Workspace.is_deleted.is_(False),
        )
    )
    if workspace is None:
        workspace = Workspace(
            workspace_code=DEMO_WORKSPACE_CODE,
            workspace_name=DEMO_WORKSPACE_NAME,
            description=DEMO_WORKSPACE_DESCRIPTION,
            status="active",
            owner_user_id=admin.id,
            created_by=admin.id,
            updated_by=admin.id,
        )
        db.add(workspace)
    else:
        workspace.workspace_name = DEMO_WORKSPACE_NAME
        workspace.description = DEMO_WORKSPACE_DESCRIPTION
        workspace.status = "active"
        workspace.updated_by = admin.id
    db.commit()
    db.refresh(workspace)
    return workspace


def _ensure_demo_workspace_admin_membership(db, *, workspace_id: int, admin: User) -> None:
    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == admin.id,
        )
    )
    if member is None:
        db.add(
            WorkspaceMember(
                workspace_id=workspace_id,
                user_id=admin.id,
                workspace_role="workspace_admin",
                status="active",
            )
        )
    else:
        member.workspace_role = "workspace_admin"
        member.status = "active"
    db.commit()


def _ensure_demo_environment_profile(db, *, workspace_id: int, admin: User) -> EnvironmentProfile:
    settings = get_settings()
    profile = db.scalar(
        select(EnvironmentProfile).where(
            EnvironmentProfile.workspace_id == workspace_id,
            EnvironmentProfile.profile_name == DEMO_ENV_PROFILE_NAME,
            EnvironmentProfile.is_deleted.is_(False),
        )
    )
    if profile is None:
        profile = EnvironmentProfile(
            workspace_id=workspace_id,
            profile_name=DEMO_ENV_PROFILE_NAME,
            base_url=settings.demo_target_base_url,
            description=DEMO_ENV_PROFILE_DESCRIPTION,
            status="active",
            created_by=admin.id,
            updated_by=admin.id,
        )
        db.add(profile)
    else:
        profile.base_url = settings.demo_target_base_url
        profile.description = DEMO_ENV_PROFILE_DESCRIPTION
        profile.status = "active"
        profile.updated_by = admin.id
    db.commit()
    db.refresh(profile)
    return profile


def _ensure_demo_device_profile(db, *, workspace_id: int, admin: User) -> DeviceProfile:
    profiles = db.scalars(
        select(DeviceProfile).where(
            DeviceProfile.workspace_id == workspace_id,
            DeviceProfile.is_deleted.is_(False),
        )
    ).all()
    target = next((profile for profile in profiles if profile.profile_name == DEMO_DEVICE_PROFILE_NAME), None)
    for profile in profiles:
        profile.is_default = profile is target
    if target is None:
        target = DeviceProfile(
            workspace_id=workspace_id,
            profile_name=DEMO_DEVICE_PROFILE_NAME,
            device_type="desktop",
            viewport_width=1440,
            viewport_height=960,
            device_scale_factor=1.0,
            user_agent=None,
            is_default=True,
            created_by=admin.id,
            updated_by=admin.id,
        )
        db.add(target)
    else:
        target.device_type = "desktop"
        target.viewport_width = 1440
        target.viewport_height = 960
        target.device_scale_factor = 1.0
        target.user_agent = None
        target.is_default = True
        target.updated_by = admin.id
    db.commit()
    db.refresh(target)
    return target


def _ensure_demo_placeholder_media(db, *, workspace_id: int, admin: User):
    from app.services.assets import create_media_object_from_bytes

    return create_media_object_from_bytes(
        db,
        user=admin,
        workspace_id=workspace_id,
        file_bytes=DEMO_PLACEHOLDER_PNG_BYTES,
        file_name="demo-template-placeholder.png",
        mime_type="image/png",
        usage="baseline",
        remark="seeded-demo-template-placeholder",
    )


def _ensure_demo_template(db, *, workspace_id: int, admin: User, media_object_id: int) -> Template:
    template = db.scalar(
        select(Template).where(
            Template.workspace_id == workspace_id,
            Template.template_code == DEMO_TEMPLATE_CODE,
            Template.is_deleted.is_(False),
        )
    )
    if template is None:
        template = Template(
            workspace_id=workspace_id,
            template_code=DEMO_TEMPLATE_CODE,
            template_name=DEMO_TEMPLATE_NAME,
            template_type="page",
            match_strategy="template",
            threshold_value=0.95,
            status="draft",
            created_by=admin.id,
            updated_by=admin.id,
        )
        db.add(template)
        db.flush()
    else:
        template.template_name = DEMO_TEMPLATE_NAME
        template.template_type = "page"
        template.match_strategy = "template"
        template.threshold_value = 0.95
        template.status = "draft"
        template.updated_by = admin.id

    current_baseline = db.scalar(
        select(BaselineRevision).where(
            BaselineRevision.template_id == template.id,
            BaselineRevision.is_current.is_(True),
        )
    )
    matching_baseline = db.scalar(
        select(BaselineRevision)
        .where(
            BaselineRevision.template_id == template.id,
            BaselineRevision.media_object_id == media_object_id,
        )
        .order_by(BaselineRevision.revision_no.desc())
    )
    if current_baseline is None or current_baseline.media_object_id != media_object_id:
        db.execute(
            update(BaselineRevision)
            .where(BaselineRevision.template_id == template.id, BaselineRevision.is_current.is_(True))
            .values(is_current=False)
        )
        if matching_baseline is None:
            next_revision = (
                db.scalar(select(func.max(BaselineRevision.revision_no)).where(BaselineRevision.template_id == template.id)) or 0
            ) + 1
            matching_baseline = BaselineRevision(
                template_id=template.id,
                revision_no=int(next_revision),
                media_object_id=media_object_id,
                source_type="seeded",
                is_current=True,
                remark="Seeded placeholder baseline for demo workspace.",
                created_by=admin.id,
            )
            db.add(matching_baseline)
            db.flush()
        else:
            matching_baseline.is_current = True
            matching_baseline.remark = "Seeded placeholder baseline for demo workspace."
        template.current_baseline_revision_id = matching_baseline.id
    else:
        template.current_baseline_revision_id = current_baseline.id

    db.commit()
    db.refresh(template)
    return template


def _ensure_demo_test_case(db, *, workspace_id: int, admin: User) -> TestCase:
    test_case = db.scalar(
        select(TestCase).where(
            TestCase.workspace_id == workspace_id,
            TestCase.case_code == DEMO_CASE_CODE,
            TestCase.is_deleted.is_(False),
        )
    )
    if test_case is None:
        test_case = TestCase(
            workspace_id=workspace_id,
            case_code=DEMO_CASE_CODE,
            case_name=DEMO_CASE_NAME,
            status="published",
            priority="p1",
            description="Seeded smoke case for first-start acceptance.",
            created_by=admin.id,
            updated_by=admin.id,
        )
        db.add(test_case)
    else:
        test_case.case_name = DEMO_CASE_NAME
        test_case.status = "published"
        test_case.priority = "p1"
        test_case.description = "Seeded smoke case for first-start acceptance."
        test_case.updated_by = admin.id
    db.commit()
    db.refresh(test_case)
    return test_case


def _replace_demo_case_steps(db, *, test_case_id: int) -> None:
    db.execute(delete(TestCaseStep).where(TestCaseStep.test_case_id == test_case_id))
    for item in DEMO_CASE_STEPS:
        db.add(
            TestCaseStep(
                test_case_id=test_case_id,
                step_no=item["step_no"],
                step_type=item["step_type"],
                step_name=item["step_name"],
                payload_json=item["payload_json"],
                timeout_ms=15000,
                retry_times=0,
            )
        )
    db.commit()


def _ensure_demo_test_suite(db, *, workspace_id: int, admin: User) -> TestSuite:
    suite = db.scalar(
        select(TestSuite).where(
            TestSuite.workspace_id == workspace_id,
            TestSuite.suite_code == DEMO_SUITE_CODE,
            TestSuite.is_deleted.is_(False),
        )
    )
    if suite is None:
        suite = TestSuite(
            workspace_id=workspace_id,
            suite_code=DEMO_SUITE_CODE,
            suite_name=DEMO_SUITE_NAME,
            status="active",
            description="Seeded smoke suite for first-start acceptance.",
            created_by=admin.id,
            updated_by=admin.id,
        )
        db.add(suite)
    else:
        suite.suite_name = DEMO_SUITE_NAME
        suite.status = "active"
        suite.description = "Seeded smoke suite for first-start acceptance."
        suite.updated_by = admin.id
    db.commit()
    db.refresh(suite)
    return suite


def _replace_demo_suite_cases(db, *, test_suite_id: int, test_case_id: int) -> None:
    db.execute(delete(SuiteCase).where(SuiteCase.test_suite_id == test_suite_id))
    db.add(SuiteCase(test_suite_id=test_suite_id, test_case_id=test_case_id, sort_order=1))
    db.commit()


def should_auto_create_database(database_url: URL) -> bool:
    settings = get_settings()
    return (
        settings.app_env == "development"
        and settings.database_auto_create
        and database_url.get_backend_name() == "postgresql"
        and database_url.database == "AutoTestDev"
    )


def resolve_admin_database_url(database_url: URL) -> URL:
    settings = get_settings()
    if settings.database_admin_url:
        return make_url(settings.database_admin_url)
    return database_url.set(database="postgres")


def validate_database_name(database_name: str) -> None:
    if not DATABASE_NAME_PATTERN.fullmatch(database_name):
        raise RuntimeError(
            "Unsafe database name detected. Only letters, numbers and underscores are allowed for auto-created databases."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the application database.")
    parser.add_argument("--skip-create-db", action="store_true", help="Do not create the database before migrations.")
    parser.add_argument("--skip-migrate", action="store_true", help="Do not run Alembic migrations.")
    parser.add_argument("--skip-seed-admin", action="store_true", help="Do not create the default admin user.")
    parser.add_argument("--skip-seed-demo-data", action="store_true", help="Do not create the seeded demo acceptance data.")
    args = parser.parse_args()
    initialize_database(
        ensure_database=not args.skip_create_db,
        run_migrations=not args.skip_migrate,
        seed_admin=not args.skip_seed_admin,
        seed_demo_data=not args.skip_seed_demo_data,
    )


if __name__ == "__main__":
    main()
