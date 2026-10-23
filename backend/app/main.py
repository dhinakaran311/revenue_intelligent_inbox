"""Revenue Intelligence Inbox — FastAPI application entry point.

Configuration:
  - CORS: exact FRONTEND_ORIGIN only (no wildcard) — DATA RULE 10
  - Global exception handler returns JSON errors without leaking secrets
  - Startup event logs app_env and base_url (no secrets logged)
  - All routers mounted with versioned-neutral prefixes

Analysis: reviewed (prepared) analyses are applied per source revision; an
optional runtime path (Groq) is exposed at /records/{type}/{id}/analysis/refresh.
"""
from __future__ import annotations

import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import ENV, app_env
from app.routers import admin, brief, exports, imports, metrics, records

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    env = app_env()
    base_url = ENV.get("BASE_URL", "http://localhost:8000")
    frontend = ENV.get("FRONTEND_ORIGIN", "(not set)")
    logger.info(
        "Revenue Intelligence Inbox starting — env=%s base_url=%s frontend_origin=%s",
        env,
        base_url,
        frontend,
        # Secrets are never logged; only these safe env values are emitted.
    )
    yield
    # Shutdown
    logger.info("Revenue Intelligence Inbox shutting down")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    _app = FastAPI(
        title="Revenue Intelligence Inbox API",
        description=(
            "Backend API for the Volopay Revenue Intelligence Inbox. "
            "Manages call/meeting records, analyses, manual route decisions, "
            "import/export, and dashboard metrics."
        ),
        version="3.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # -------------------------------------------------------------------
    # CORS — exact origin only (DATA RULE 10: no wildcard)
    # -------------------------------------------------------------------
    # FRONTEND_ORIGIN may list several exact origins, comma-separated
    # (e.g. the Vercel URL and http://localhost:3000). Never a wildcard.
    origins = [o.strip() for o in ENV.get("FRONTEND_ORIGIN", "http://localhost:3000").split(",") if o.strip()]
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -------------------------------------------------------------------
    # Global exception handler — JSON error, no secrets leaked
    # -------------------------------------------------------------------
    @_app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log the full traceback internally but return a sanitised message
        logger.error(
            "Unhandled exception on %s %s: %s",
            request.method,
            request.url.path,
            type(exc).__name__,
        )
        logger.debug(traceback.format_exc())
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred. Please try again.",
                "type": type(exc).__name__,
            },
        )

    # -------------------------------------------------------------------
    # Routers
    # -------------------------------------------------------------------
    _app.include_router(records.router)
    _app.include_router(metrics.router)
    _app.include_router(imports.router)
    _app.include_router(exports.router)
    _app.include_router(admin.router)
    _app.include_router(brief.router)

    # -------------------------------------------------------------------
    # Root probe (for load-balancer / k8s liveness)
    # -------------------------------------------------------------------
    @_app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {"service": "revenue-intelligence-inbox", "version": "3.0.0", "status": "ok"}

    return _app


app = create_app()
