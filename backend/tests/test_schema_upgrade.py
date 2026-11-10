import os
import unittest
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("OPENAI_API_KEY", "test-unused-key")

from alembic import command
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app import schema_upgrade
from app.database import Base

HEAD = ScriptDirectory(str(schema_upgrade.BACKEND_DIR / "alembic")).get_current_head()
NEW_TABLES = ("customer_onboarding", "activation_jobs")
NEW_CONFIG_COLUMNS = ("trusted_flow_id", "trusted_agent_id", "trusted_routing_enabled")


class SchemaUpgradeTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.addCleanup(self.engine.dispose)

    def revision(self):
        with self.engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()

    def make_pre_alembic_database(self):
        """The production shape: core tables exist, onboarding schema and Alembic history do not."""
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            for table in ("activation_jobs", "customer_onboarding"):
                connection.execute(text(f"DROP TABLE {table}"))
            for column in NEW_CONFIG_COLUMNS:
                connection.execute(text(f"ALTER TABLE rootcall_configs DROP COLUMN {column}"))

    def test_pre_alembic_database_gets_the_missing_tables_and_columns(self):
        self.make_pre_alembic_database()
        inspector = inspect(self.engine)
        self.assertFalse(any(inspector.has_table(name) for name in NEW_TABLES))
        self.assertIsNone(self.revision())

        self.assertEqual(schema_upgrade.upgrade_schema(self.engine), "baselined")

        inspector = inspect(self.engine)
        for name in NEW_TABLES:
            self.assertTrue(inspector.has_table(name), name)
        columns = {column["name"] for column in inspector.get_columns("rootcall_configs")}
        self.assertTrue(set(NEW_CONFIG_COLUMNS) <= columns)
        self.assertEqual(self.revision(), HEAD)
        self.assertEqual(schema_upgrade.upgrade_schema(self.engine), "current")

    def test_existing_customer_data_survives_the_upgrade(self):
        self.make_pre_alembic_database()
        with self.engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO users (id, email, username, hashed_password, is_active, balance) "
                "VALUES (76, 'old@example.com', 'old@example.com', 'x', 1, 0)"
            ))
        schema_upgrade.upgrade_schema(self.engine)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT email FROM users WHERE id = 76")).scalar(), "old@example.com")

    def test_empty_database_is_created_at_the_latest_revision(self):
        self.assertEqual(schema_upgrade.upgrade_schema(self.engine), "created")
        self.assertTrue(inspect(self.engine).has_table("customer_onboarding"))
        self.assertEqual(self.revision(), HEAD)

    def test_unrecognised_database_is_left_untouched(self):
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        with self.assertLogs("app.schema_upgrade", "ERROR"):
            self.assertEqual(schema_upgrade.upgrade_schema(self.engine), "skipped")
        self.assertIsNone(self.revision())
        self.assertFalse(inspect(self.engine).has_table("customer_onboarding"))

    def test_failure_is_reported_never_raised(self):
        self.make_pre_alembic_database()
        with patch.object(command, "upgrade", side_effect=RuntimeError("migration exploded")), \
                self.assertLogs("app.schema_upgrade", "ERROR") as logs:
            self.assertEqual(schema_upgrade.upgrade_schema(self.engine), "failed")
        self.assertIn("alembic upgrade head", logs.output[0])

    def test_auto_migrate_can_be_disabled(self):
        self.assertTrue(schema_upgrade.auto_migrate_enabled({}))
        for value in ("false", "0", "No", " off "):
            self.assertFalse(schema_upgrade.auto_migrate_enabled({"AUTO_MIGRATE": value}))


class PostgresSchemaUpgradeTest(unittest.TestCase):
    """Opt-in: set TEST_SCHEMA_POSTGRES_URL to a throwaway PostgreSQL database (it is wiped)."""

    URL = os.environ.get("TEST_SCHEMA_POSTGRES_URL")

    def setUp(self):
        if not self.URL:
            self.skipTest("Set TEST_SCHEMA_POSTGRES_URL to an isolated PostgreSQL database")
        self.engine = create_engine(self.URL)
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            connection.execute(text("DROP TABLE activation_jobs, customer_onboarding"))
            for column in NEW_CONFIG_COLUMNS:
                connection.execute(text(f"ALTER TABLE rootcall_configs DROP COLUMN {column}"))

    def test_upgrade_and_concurrent_instances(self):
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=3) as pool:
            results = sorted(pool.map(lambda _: schema_upgrade.upgrade_schema(self.engine), range(3)))
        self.assertEqual(results, ["baselined", "current", "current"])
        inspector = inspect(self.engine)
        for name in NEW_TABLES:
            self.assertTrue(inspector.has_table(name), name)
        with self.engine.connect() as connection:
            self.assertEqual(MigrationContext.configure(connection).get_current_revision(), HEAD)

    def test_failure_rolls_back_atomically(self):
        with patch.object(command, "upgrade", side_effect=RuntimeError("boom")), \
                self.assertLogs("app.schema_upgrade", "ERROR"):
            self.assertEqual(schema_upgrade.upgrade_schema(self.engine), "failed")
        inspector = inspect(self.engine)
        self.assertFalse(inspector.has_table("alembic_version"))
        self.assertFalse(any(inspector.has_table(name) for name in NEW_TABLES))


if __name__ == "__main__":
    unittest.main()
