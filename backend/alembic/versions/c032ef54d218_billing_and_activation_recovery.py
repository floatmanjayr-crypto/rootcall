"""Persist billing visibility and reviewed activation recovery."""
from alembic import op
import sqlalchemy as sa

revision = "c032ef54d218"
down_revision = "b921df43c107"
branch_labels = None
depends_on = None


def upgrade():
    for column in (
        sa.Column("subscription_status", sa.String(30)),
        sa.Column("current_period_end", sa.DateTime()),
        sa.Column("cancel_at", sa.DateTime()),
        sa.Column("canceled_at", sa.DateTime()),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("billing_checked_at", sa.DateTime()),
        sa.Column("payment_issue_since", sa.DateTime()),
        sa.Column("activation_stage", sa.String(100)),
        sa.Column("activation_updated_at", sa.DateTime()),
        sa.Column("uncertain_operation", sa.String(40)),
        sa.Column("recovery_reviewed_at", sa.DateTime()),
        sa.Column("recovery_reviewed_by", sa.Integer(), sa.ForeignKey(
            "users.id", name="fk_onboarding_recovery_reviewer",
        )),
        sa.Column("recovery_note", sa.String(500)),
    ):
        with op.batch_alter_table("customer_onboarding") as batch:
            batch.add_column(column)
    op.execute(sa.text(
        "UPDATE customer_onboarding SET activation_updated_at = updated_at "
        "WHERE status IN ('provisioning', 'error')"
    ))


def downgrade():
    with op.batch_alter_table("customer_onboarding") as batch:
        for name in (
            "recovery_note", "recovery_reviewed_by", "recovery_reviewed_at",
            "uncertain_operation", "activation_updated_at", "activation_stage", "payment_issue_since",
            "billing_checked_at", "cancel_at_period_end", "canceled_at", "cancel_at", "current_period_end",
            "subscription_status",
        ):
            batch.drop_column(name)
