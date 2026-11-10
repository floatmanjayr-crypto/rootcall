"""Make the existing dashboard voice preference available to activation workers."""
from alembic import op
import sqlalchemy as sa

revision = "e254ab76f430"
down_revision = "d143fa65e329"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("rootcall_configs")}
    if "voice_id" not in columns:
        op.add_column("rootcall_configs", sa.Column(
            "voice_id", sa.String(), nullable=False, server_default="11labs-Adrian",
        ))


def downgrade():
    # This column also exists in releases predating this migration.
    # Retain saved preferences when rolling back automated activation.
    pass
