"""Persist confirmed activation jobs and customer-reported setup checks."""
from alembic import op
import sqlalchemy as sa

revision = "d143fa65e329"
down_revision = "c032ef54d218"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "activation_jobs",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_error", sa.String(500)),
    )
    op.create_index("ix_activation_jobs_status", "activation_jobs", ["status"])
    op.create_index("ix_activation_jobs_available_at", "activation_jobs", ["available_at"])
    op.add_column("customer_onboarding", sa.Column("service_setup", sa.JSON()))


def downgrade():
    with op.batch_alter_table("customer_onboarding") as batch:
        batch.drop_column("service_setup")
    op.drop_table("activation_jobs")
