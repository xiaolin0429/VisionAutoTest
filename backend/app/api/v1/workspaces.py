from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.device_profiles import router as device_profiles_router
from app.api.v1.environment_profiles import router as environment_profiles_router
from app.api.v1.environment_variables import router as environment_variables_router
from app.api.v1.workspace_execution_readiness import (
    router as workspace_execution_readiness_router,
)
from app.api.v1.workspace_management import router as workspace_management_router
from app.api.v1.workspace_members import router as workspace_members_router

router = APIRouter(tags=["workspaces"])
# Aggregation router only: concrete workspace sub-resources live in dedicated modules below.
router.include_router(workspace_management_router)
router.include_router(workspace_execution_readiness_router)
router.include_router(workspace_members_router)
router.include_router(environment_profiles_router)
router.include_router(environment_variables_router)
router.include_router(device_profiles_router)
