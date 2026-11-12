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


# (group, label, required environment variables). Names only are ever reported, never values.
SETTING_GROUPS = (
    ("Public site address", "Stripe returns, password-reset emails and webhooks", ("APP_BASE_URL",)),
    ("Payments", "Stripe checkout and subscription checks",
     ("STRIPE_SECRET_KEY", "STRIPE_ESSENTIAL_PRICE_ID", "STRIPE_WEBHOOK_SECRET")),
    ("Phone routing", "Buying numbers and connecting them to the AI assistant", ("TELNYX_API_KEY",)),
    ("AI assistant", "Creating the screening assistant and listing voices", ("RETELL_API_KEY",)),
)


def _configured(settings, name):
    return bool(str(getattr(settings, name, "") or os.getenv(name, "")).strip())


def service_readiness(settings, engine=None):
    """Report which settings and tables a customer activation needs but the service lacks."""
    groups = []
    for title, purpose, names in SETTING_GROUPS:
        if not getattr(settings, "AUTOMATED_ONBOARDING", False):
            # The webhook only finalizes automated onboarding payments.
            names = tuple(name for name in names if name != "STRIPE_WEBHOOK_SECRET")
        missing = [name for name in names if not _configured(settings, name)]
        if names == ("APP_BASE_URL",) and not missing:
            if not str(getattr(settings, "APP_BASE_URL", "")).strip().startswith("https://"):
                missing = ["APP_BASE_URL (must start with https://)"]
        groups.append({"name": title, "purpose": purpose, "ok": not missing, "missing": missing})
    if engine is not None:
        try:
            absent = missing_tables(engine)
        except Exception:
            absent = ["could not inspect the database"]
        groups.append({
            "name": "Database", "purpose": "Saved setup progress and activation jobs",
            "ok": not absent, "missing": absent,
        })
    return groups


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


def log_deployment_readiness(engine, base_url, settings=None):
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
    if settings is not None:
        for group in service_readiness(settings):
            if not group["ok"]:
                log.warning(
                    "Setup incomplete - %s (%s): set %s in the Render environment.",
                    group["name"], group["purpose"], ", ".join(group["missing"]),
                )


def register_error_handlers(app: FastAPI):
    @app.exception_handler(OperationalError)
    @app.exception_handler(ProgrammingError)
    async def database_unavailable(request: Request, error: Exception):
        log.error("Database error on %s %s: %s", request.method, request.url.path, error.__class__.__name__,
                  exc_info=error)
        return JSONResponse(status_code=503, content={"detail": UNAVAILABLE_MESSAGE})
