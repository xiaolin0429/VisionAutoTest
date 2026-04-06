from fastapi import APIRouter

from app.api.v1.assets import router as assets_router
from app.api.v1.cases import router as cases_router
from app.api.v1.executions import router as executions_router
from app.api.v1.iam import router as iam_router
from app.api.v1.workspaces import router as workspaces_router

api_router = APIRouter()
# Top-level API aggregation router. Domain behavior lives in the included resource routers.
api_router.include_router(iam_router)
api_router.include_router(workspaces_router)
api_router.include_router(assets_router)
api_router.include_router(cases_router)
api_router.include_router(executions_router)
