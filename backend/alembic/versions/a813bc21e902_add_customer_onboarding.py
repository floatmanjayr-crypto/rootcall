"""Persist payment-verified customer onboarding and provisioning checkpoints."""
from alembic import op
import sqlalchemy as sa

revision = "a813bc21e902"
down_revision = "40508a9fb685"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "customer_onboarding",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("first_name", sa.String(100)),
        sa.Column("last_name", sa.String(100)),
        sa.Column("forwarding_number", sa.String(16)),
        sa.Column("voice_id", sa.String(200)),
        sa.Column("shield_number", sa.String(16), unique=True),
        sa.Column("trusted_contacts", sa.JSON()),
        sa.Column("tier", sa.String(20)),
        sa.Column("checkout_key", sa.String(64), nullable=False),
        sa.Column("checkout_session_id", sa.String(255), unique=True),
        sa.Column("stripe_customer_id", sa.String(255)),
        sa.Column("stripe_subscription_id", sa.String(255), unique=True),
        sa.Column("payment_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("order_attempted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("connection_id", sa.String(255)),
        sa.Column("llm_id", sa.String(255)),
        sa.Column("agent_id", sa.String(255)),
        sa.Column("transfer_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("number_imported", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_message", sa.String(500)),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("customer_onboarding")
