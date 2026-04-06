from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.http import ApiError
from app.core.security import decrypt_sensitive_value, encrypt_sensitive_value
from app.models import (
    DeviceProfile,
    EnvironmentProfile,
    EnvironmentVariable,
    User,
    Workspace,
    WorkspaceMember,
)
from app.services.helpers import (
    apply_keyword,
    count_total,
    require_user,
    require_workspace,
    require_workspace_access,
    require_workspace_admin,
    validate_ordered_sequence,
)


def _workspace_member_row(
    db: Session, *, workspace_id: int, user_id: int
) -> WorkspaceMember | None:
    """Fetch a workspace-member row for one user inside one workspace.

    Args:
        db: Active database session.
        workspace_id: Workspace being inspected.
        user_id: User whose membership row should be loaded.

    Returns:
        The matching membership row, or ``None`` when no row exists.
    """
    return db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )


def list_workspaces(
    db: Session,
    *,
    user: User,
    page: int,
    page_size: int,
    status: str | None,
    keyword: str | None,
):
    """List workspaces visible to the current user with optional filtering.

    Args:
        db: Active database session.
        user: Current user requesting the workspace list.
        page: 1-based page number.
        page_size: Maximum items returned for the page.
        status: Optional workspace status filter.
        keyword: Optional keyword matched against code/name fields.

    Returns:
        A tuple of ``(items, total)`` for paginated workspace listing.
    """
    accessible_ids = select(WorkspaceMember.workspace_id).where(
        WorkspaceMember.user_id == user.id, WorkspaceMember.status == "active"
    )
    stmt = select(Workspace).where(
        Workspace.is_deleted.is_(False),
        (Workspace.owner_user_id == user.id) | (Workspace.id.in_(accessible_ids)),
    )
    if status:
        stmt = stmt.where(Workspace.status == status)
    stmt = apply_keyword(
        stmt, keyword, Workspace.workspace_code, Workspace.workspace_name
    )
    total = count_total(db, stmt)
    items = db.scalars(
        stmt.order_by(Workspace.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return items, total


def create_workspace(
    db: Session,
    *,
    user: User,
    workspace_code: str,
    name: str,
    description: str | None,
    status: str,
) -> Workspace:
    """Create a workspace and seed the owner as the first workspace admin.

    Args:
        db: Active database session.
        user: User creating and owning the workspace.
        workspace_code: Unique workspace code.
        name: Human-readable workspace name.
        description: Optional workspace description.
        status: Initial workspace status.

    Returns:
        The newly created workspace entity.

    Raises:
        ApiError: If the workspace code already exists.
    """
    existing = db.scalar(
        select(Workspace).where(
            Workspace.workspace_code == workspace_code, Workspace.is_deleted.is_(False)
        )
    )
    if existing is not None:
        raise ApiError(
            code="WORKSPACE_CODE_EXISTS",
            message="Workspace code already exists.",
            status_code=409,
        )
    workspace = Workspace(
        workspace_code=workspace_code,
        workspace_name=name,
        description=description,
        status=status,
        owner_user_id=user.id,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(workspace)
    db.flush()
    db.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            workspace_role="workspace_admin",
            status="active",
        )
    )
    db.commit()
    db.refresh(workspace)
    return workspace


def update_workspace(
    db: Session,
    workspace: Workspace,
    *,
    user: User,
    name: str | None,
    description: str | None,
    status: str | None,
) -> Workspace:
    """Update editable workspace fields after admin permission check.

    Args:
        db: Active database session.
        workspace: Workspace being updated.
        user: User requesting the update.
        name: Optional replacement workspace name.
        description: Optional replacement description.
        status: Optional replacement status.

    Returns:
        The refreshed workspace entity.
    """
    require_workspace_admin(db, user, workspace.id)
    if name is not None:
        workspace.workspace_name = name
    if description is not None:
        workspace.description = description
    if status is not None:
        workspace.status = status
    workspace.updated_by = user.id
    db.commit()
    db.refresh(workspace)
    return workspace


def list_members(db: Session, *, user: User, workspace_id: int):
    require_workspace_access(db, user, workspace_id)
    return db.scalars(
        select(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.id.asc())
    ).all()


def add_member(
    db: Session, *, user: User, workspace_id: int, user_id: int, workspace_role: str
) -> WorkspaceMember:
    require_workspace_admin(db, user, workspace_id)
    require_user(db, user_id)
    existing = _workspace_member_row(db, workspace_id=workspace_id, user_id=user_id)
    if existing is not None:
        raise ApiError(
            code="WORKSPACE_MEMBER_EXISTS",
            message="Workspace member already exists.",
            status_code=409,
        )
    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=user_id,
        workspace_role=workspace_role,
        status="active",
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def update_member(
    db: Session,
    *,
    user: User,
    member: WorkspaceMember,
    workspace_role: str | None,
    status: str | None,
) -> WorkspaceMember:
    require_workspace_admin(db, user, member.workspace_id)
    if workspace_role is not None:
        member.workspace_role = workspace_role
    if status is not None:
        member.status = status
    _guard_last_admin(db, member.workspace_id, member.id, workspace_role, status)
    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, *, user: User, member: WorkspaceMember) -> None:
    require_workspace_admin(db, user, member.workspace_id)
    _guard_last_admin(
        db, member.workspace_id, member.id, "workspace_member", "inactive"
    )
    db.delete(member)
    db.commit()


def _guard_last_admin(
    db: Session,
    workspace_id: int,
    target_member_id: int,
    next_role: str | None,
    next_status: str | None,
) -> None:
    admins = db.scalars(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.workspace_role == "workspace_admin",
            WorkspaceMember.status == "active",
        )
    ).all()
    if len(admins) != 1:
        return
    last_admin = admins[0]
    if last_admin.id != target_member_id:
        return
    if next_role == "workspace_admin" and next_status in (None, "active"):
        return
    raise ApiError(
        code="WORKSPACE_LAST_ADMIN_PROTECTED",
        message="The last workspace admin cannot be removed.",
        status_code=422,
    )


def get_member(db: Session, member_id: int) -> WorkspaceMember:
    member = db.get(WorkspaceMember, member_id)
    if member is None:
        raise ApiError(
            code="WORKSPACE_MEMBER_NOT_FOUND",
            message="Workspace member not found.",
            status_code=404,
        )
    return member


def list_environment_profiles(
    db: Session, *, user: User, workspace_id: int, page: int, page_size: int
):
    require_workspace_access(db, user, workspace_id)
    stmt = select(EnvironmentProfile).where(
        EnvironmentProfile.workspace_id == workspace_id,
        EnvironmentProfile.is_deleted.is_(False),
    )
    total = count_total(db, stmt)
    items = db.scalars(
        stmt.order_by(EnvironmentProfile.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return items, total


def create_environment_profile(
    db: Session,
    *,
    user: User,
    workspace_id: int,
    profile_name: str,
    base_url: str,
    description: str | None,
    status: str,
) -> EnvironmentProfile:
    """Create an environment profile inside the given workspace.

    Args:
        db: Active database session.
        user: User creating the environment profile.
        workspace_id: Workspace that will own the profile.
        profile_name: Unique profile name inside the workspace.
        base_url: Target application base URL used by test execution.
        description: Optional profile description.
        status: Initial profile status.

    Returns:
        The newly created environment profile.

    Raises:
        ApiError: If another active profile in the workspace already uses the same name.
    """
    require_workspace_access(db, user, workspace_id)
    existing = db.scalar(
        select(EnvironmentProfile).where(
            EnvironmentProfile.workspace_id == workspace_id,
            EnvironmentProfile.profile_name == profile_name,
            EnvironmentProfile.is_deleted.is_(False),
        )
    )
    if existing is not None:
        raise ApiError(
            code="ENVIRONMENT_PROFILE_NAME_EXISTS",
            message="Environment profile name already exists.",
            status_code=409,
        )
    profile = EnvironmentProfile(
        workspace_id=workspace_id,
        profile_name=profile_name,
        base_url=base_url,
        description=description,
        status=status,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_environment_profile(
    db: Session, environment_profile_id: int
) -> EnvironmentProfile:
    profile = db.get(EnvironmentProfile, environment_profile_id)
    if profile is None or profile.is_deleted:
        raise ApiError(
            code="ENVIRONMENT_PROFILE_NOT_FOUND",
            message="Environment profile not found.",
            status_code=404,
        )
    return profile


def update_environment_profile(
    db: Session,
    *,
    user: User,
    profile: EnvironmentProfile,
    profile_name: str | None,
    base_url: str | None,
    description: str | None,
    status: str | None,
) -> EnvironmentProfile:
    require_workspace_access(db, user, profile.workspace_id)
    if profile_name is not None:
        profile.profile_name = profile_name
    if base_url is not None:
        profile.base_url = base_url
    if description is not None:
        profile.description = description
    if status is not None:
        profile.status = status
    profile.updated_by = user.id
    db.commit()
    db.refresh(profile)
    return profile


def delete_environment_profile(
    db: Session, *, user: User, profile: EnvironmentProfile
) -> None:
    require_workspace_access(db, user, profile.workspace_id)
    profile.is_deleted = True
    db.commit()


def list_environment_variables(db: Session, *, user: User, profile: EnvironmentProfile):
    require_workspace_access(db, user, profile.workspace_id)
    return db.scalars(
        select(EnvironmentVariable)
        .where(EnvironmentVariable.environment_profile_id == profile.id)
        .order_by(EnvironmentVariable.id.asc())
    ).all()


def create_environment_variable(
    db: Session,
    *,
    user: User,
    profile: EnvironmentProfile,
    var_key: str,
    value: str,
    is_secret: bool,
    description: str | None,
) -> EnvironmentVariable:
    """Create one environment variable under an environment profile.

    Args:
        db: Active database session.
        user: User creating the variable.
        profile: Parent environment profile.
        var_key: Unique variable key inside the profile.
        value: Plaintext value to persist, encrypted at rest.
        is_secret: Whether the value should be masked in API responses.
        description: Optional operator-facing description.

    Returns:
        The newly created environment variable entity.

    Raises:
        ApiError: If the profile already contains the same variable key.
    """
    require_workspace_access(db, user, profile.workspace_id)
    existing = db.scalar(
        select(EnvironmentVariable).where(
            EnvironmentVariable.environment_profile_id == profile.id,
            EnvironmentVariable.var_key == var_key,
        )
    )
    if existing is not None:
        raise ApiError(
            code="ENVIRONMENT_VARIABLE_KEY_EXISTS",
            message="Environment variable key already exists.",
            status_code=409,
        )
    variable = EnvironmentVariable(
        environment_profile_id=profile.id,
        var_key=var_key,
        var_value_ciphertext=encrypt_sensitive_value(value),
        is_secret=is_secret,
        description=description,
    )
    db.add(variable)
    db.commit()
    db.refresh(variable)
    return variable


def get_environment_variable(
    db: Session, environment_variable_id: int
) -> EnvironmentVariable:
    variable = db.get(EnvironmentVariable, environment_variable_id)
    if variable is None:
        raise ApiError(
            code="ENVIRONMENT_VARIABLE_NOT_FOUND",
            message="Environment variable not found.",
            status_code=404,
        )
    return variable


def update_environment_variable(
    db: Session,
    *,
    user: User,
    variable: EnvironmentVariable,
    value: str | None,
    is_secret: bool | None,
    description: str | None,
) -> EnvironmentVariable:
    profile = get_environment_profile(db, variable.environment_profile_id)
    require_workspace_access(db, user, profile.workspace_id)
    if value is not None:
        variable.var_value_ciphertext = encrypt_sensitive_value(value)
    if is_secret is not None:
        variable.is_secret = is_secret
    if description is not None:
        variable.description = description
    db.commit()
    db.refresh(variable)
    return variable


def delete_environment_variable(
    db: Session, *, user: User, variable: EnvironmentVariable
) -> None:
    profile = get_environment_profile(db, variable.environment_profile_id)
    require_workspace_access(db, user, profile.workspace_id)
    db.delete(variable)
    db.commit()


def environment_variable_view(variable: EnvironmentVariable) -> dict:
    """Build the response payload for one environment variable.

    Args:
        variable: Persisted environment variable entity.

    Returns:
        A response dict with masked or decrypted display value depending on secrecy.
    """
    display_value = (
        "******"
        if variable.is_secret
        else decrypt_sensitive_value(variable.var_value_ciphertext)
    )
    payload = {
        "id": variable.id,
        "environment_profile_id": variable.environment_profile_id,
        "var_key": variable.var_key,
        "is_secret": variable.is_secret,
        "description": variable.description,
        "created_at": variable.created_at,
        "updated_at": variable.updated_at,
        "display_value": display_value,
    }
    return payload


def list_device_profiles(
    db: Session, *, user: User, workspace_id: int, page: int, page_size: int
):
    require_workspace_access(db, user, workspace_id)
    stmt = select(DeviceProfile).where(
        DeviceProfile.workspace_id == workspace_id, DeviceProfile.is_deleted.is_(False)
    )
    total = count_total(db, stmt)
    items = db.scalars(
        stmt.order_by(DeviceProfile.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return items, total


def create_device_profile(
    db: Session,
    *,
    user: User,
    workspace_id: int,
    profile_name: str,
    device_type: str,
    viewport_width: int,
    viewport_height: int,
    device_scale_factor: float,
    user_agent: str | None,
    is_default: bool,
) -> DeviceProfile:
    require_workspace_access(db, user, workspace_id)
    if is_default:
        _clear_default_device_profile(db, workspace_id)
    profile = DeviceProfile(
        workspace_id=workspace_id,
        profile_name=profile_name,
        device_type=device_type,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        device_scale_factor=device_scale_factor,
        user_agent=user_agent,
        is_default=is_default,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_device_profile(db: Session, device_profile_id: int) -> DeviceProfile:
    profile = db.get(DeviceProfile, device_profile_id)
    if profile is None or profile.is_deleted:
        raise ApiError(
            code="DEVICE_PROFILE_NOT_FOUND",
            message="Device profile not found.",
            status_code=404,
        )
    return profile


def update_device_profile(
    db: Session,
    *,
    user: User,
    profile: DeviceProfile,
    profile_name: str | None,
    device_type: str | None,
    viewport_width: int | None,
    viewport_height: int | None,
    device_scale_factor: float | None,
    user_agent: str | None,
    is_default: bool | None,
) -> DeviceProfile:
    require_workspace_access(db, user, profile.workspace_id)
    if is_default:
        _clear_default_device_profile(db, profile.workspace_id, exclude_id=profile.id)
        profile.is_default = True
    elif is_default is not None:
        profile.is_default = False
    if profile_name is not None:
        profile.profile_name = profile_name
    if device_type is not None:
        profile.device_type = device_type
    if viewport_width is not None:
        profile.viewport_width = viewport_width
    if viewport_height is not None:
        profile.viewport_height = viewport_height
    if device_scale_factor is not None:
        profile.device_scale_factor = device_scale_factor
    if user_agent is not None:
        profile.user_agent = user_agent
    profile.updated_by = user.id
    db.commit()
    db.refresh(profile)
    return profile


def _clear_default_device_profile(
    db: Session, workspace_id: int, exclude_id: int | None = None
) -> None:
    profiles = db.scalars(
        select(DeviceProfile).where(
            DeviceProfile.workspace_id == workspace_id,
            DeviceProfile.is_default.is_(True),
            DeviceProfile.is_deleted.is_(False),
        )
    ).all()
    for profile in profiles:
        if exclude_id is not None and profile.id == exclude_id:
            continue
        profile.is_default = False
