from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import Base, engine
from app.api import (
    routes_geometry, routes_bem, routes_cfd, routes_structural, routes_composites,
    routes_fatigue, routes_aeroelastic, routes_economics, routes_optimization,
    routes_reporting, routes_validation,
)
from app.models import design  # noqa: F401 - ensures model is registered before create_all

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "Research-grade CAE platform for a Hybrid Darrieus-Savonius VAWT. "
        "Phase 1-5: architecture, geometry module, and Stage-1 BEM aerodynamic solver."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health", tags=["health"])
def health():
    return {"status": "ok", "app": settings.app_name}


app.include_router(routes_geometry.router, prefix=settings.api_v1_prefix)
app.include_router(routes_bem.router, prefix=settings.api_v1_prefix)
app.include_router(routes_cfd.router, prefix=settings.api_v1_prefix)
app.include_router(routes_structural.router, prefix=settings.api_v1_prefix)
app.include_router(routes_composites.router, prefix=settings.api_v1_prefix)
app.include_router(routes_fatigue.router, prefix=settings.api_v1_prefix)
app.include_router(routes_aeroelastic.router, prefix=settings.api_v1_prefix)
app.include_router(routes_economics.router, prefix=settings.api_v1_prefix)
app.include_router(routes_optimization.router, prefix=settings.api_v1_prefix)
app.include_router(routes_reporting.router, prefix=settings.api_v1_prefix)
app.include_router(routes_validation.router, prefix=settings.api_v1_prefix)
