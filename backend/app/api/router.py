from fastapi import APIRouter

from app.api.routes import health
from app.modules.agent.interface import routes as agent_routes
from app.modules.document.interface import routes as document_routes

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(agent_routes.router)
api_router.include_router(document_routes.router)
