"""Bring the database schema up to date at startup without risking the running app.

Render's pre-deploy command only runs for blueprint-managed paid services, so a service that is
not configured that way would otherwise serve new code against an old schema. This applies the
Alembic migrations itself, atomically (all or nothing), under a database lock so concurrent
instances cannot race, and it never raises: on any failure the app still boots and logs why.

Set AUTO_MIGRATE=false to turn it off and run `alembic upgrade head` yourself.
"""
import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

log = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[1]
# Last revision whose tables predate the onboarding work and were created outside Alembic.
BASELINE_REVISION = "40508a9fb685"
PRE_ALEMBIC_TABLES = ("users", "phone_numbers", "rootcall_configs")
LOCK_KEY = 73022


def auto_migrate_enabled(environ=os.environ):
    return environ.get("AUTO_MIGRATE", "true").strip().lower() not in {"0", "false", "no", "off"}


def _config(connection):
    config = Config()
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["connection"] = connection
    return config


def plan(connection):
    """Decide what the current database needs."""
    if MigrationContext.configure(connection).get_current_revision():
        return "upgrade"
    inspector = inspect(connection)
    if not inspector.has_table("users"):
        return "fresh"
    if all(inspector.has_table(name) for name in PRE_ALEMBIC_TABLES):
        return "baseline"
    return "unknown"


def upgrade_schema(engine):
    """Return one of: current, upgraded, baselined, created, skipped, failed."""
    locked = None
    try:
        if engine.dialect.name == "postgresql":
            locked = engine.connect()
            locked.execute(text("SELECT pg_advisory_lock(:key)"), {"key": LOCK_KEY})
        with engine.begin() as connection:
            action = plan(connection)
            config = _config(connection)
            if action == "unknown":
                log.error(
                    "Schema upgrade skipped: this database has no Alembic history and is missing core tables. "
                    "Inspect it manually before running `alembic upgrade head`."
                )
                return "skipped"
            if action == "fresh":
                import app.models  # noqa: F401  (register every table on Base.metadata)
                from app.database import Base

                Base.metadata.create_all(connection)
                command.stamp(config, "head")
                log.info("Created a new database schema at the latest revision")
                return "created"
            before = MigrationContext.configure(connection).get_current_revision()
            if action == "baseline":
                command.stamp(config, BASELINE_REVISION)
                log.warning("Database had no Alembic history; recorded baseline %s before upgrading", BASELINE_REVISION)
            command.upgrade(config, "head")
            after = MigrationContext.configure(connection).get_current_revision()
            if action == "upgrade" and before == after:
                return "current"
            log.warning("Database schema upgraded to revision %s", after)
            return "baselined" if action == "baseline" else "upgraded"
    except Exception:
        log.exception(
            "Automatic schema upgrade failed and was rolled back. The app is still running on the old schema; "
            "run `cd backend && alembic upgrade head` manually and check the error above."
        )
        return "failed"
    finally:
        if locked is not None:
            try:
                locked.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
            finally:
                locked.close()
