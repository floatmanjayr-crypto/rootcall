"""Startup diagnostics and customer-safe handling for deployment problems."""
import logging
import os
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError, ProgrammingError

log = logging.getLogger(__name__)

REQUIRED_TABLES = ("users", "customer_onboarding", "activation_jobs")
UNAVAILABLE_MESSAGE = "RootCall is temporarily unavailable. Please try again shortly or contact support."


def missing_tables(engine, required=REQUIRED_TABLES):
    inspector = inspect(engine)
    return [name for name in required if not inspector.has_table(name)]


def base_url_warnings(base_url, render_url=None):
    """Explain APP_BASE_URL problems that break Stripe returns, emails and webhooks."""
    parsed = urlparse((base_url or "").strip())
    if not parsed.netloc or parsed.scheme != "https":
        return ["APP_BASE_URL is missing or not an https URL; checkout and password-reset links will fail."]
    render_host = urlparse(render_url or "").netloc
    if render_host and parsed.netloc != render_host:
        return [
            f"APP_BASE_URL host '{parsed.netloc}' differs from this service's Render host '{render_host}'. "
            "Stripe returns, emails and webhooks go to APP_BASE_URL; confirm it serves this app."
        ]
    return []


def log_deployment_readiness(engine, base_url):
    """Log (never raise) so a misconfigured deploy is diagnosable from the Render log."""
    try:
        missing = missing_tables(engine)
        if missing:
            log.error(
                "Database is missing tables %s. Run `cd backend && alembic upgrade head` before serving customers.",
                ", ".join(missing),
            )
    except Exception:
        log.exception("Could not verify database schema at startup")
    for warning in base_url_warnings(base_url, os.getenv("RENDER_EXTERNAL_URL")):
        log.warning(warning)


def register_error_handlers(app: FastAPI):
    @app.exception_handler(OperationalError)
    @app.exception_handler(ProgrammingError)
    async def database_unavailable(request: Request, error: Exception):
        log.error("Database error on %s %s: %s", request.method, request.url.path, error.__class__.__name__,
                  exc_info=error)
        return JSONResponse(status_code=503, content={"detail": UNAVAILABLE_MESSAGE})
