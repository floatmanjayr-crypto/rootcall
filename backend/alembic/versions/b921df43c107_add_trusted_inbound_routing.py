"""Persist direct-to-Retell trusted caller routing checkpoints."""
from alembic import op
import sqlalchemy as sa

revision = "b921df43c107"
down_revision = "a813bc21e902"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("rootcall_configs", sa.Column("trusted_flow_id", sa.String(), nullable=True))
    op.add_column("rootcall_configs", sa.Column("trusted_agent_id", sa.String(), nullable=True))
    op.add_column("rootcall_configs", sa.Column(
        "trusted_routing_enabled", sa.Boolean(), nullable=False, server_default=sa.false(),
    ))


def downgrade():
    op.drop_column("rootcall_configs", "trusted_routing_enabled")
    op.drop_column("rootcall_configs", "trusted_agent_id")
    op.drop_column("rootcall_configs", "trusted_flow_id")
