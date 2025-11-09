# alembic/env.py
from logging.config import fileConfig
from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection

import os
import sys

# Make "app" importable when running `alembic` from project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- Import your app's DB + settings + models ---
from app.database import engine, Base            # <- you have app/db.py
from app.config import settings            # <- loads .env
import app.models                       # <- ensure models are imported so metadata is populated

# Alembic Config
config = context.config

# If you also keep sqlalchemy.url in alembic.ini, this line makes settings take precedence:
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a DB connection."""
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a DB connection (recommended)."""
    connectable = engine
    with connectable.connect() as connection:  # type: Connection
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
