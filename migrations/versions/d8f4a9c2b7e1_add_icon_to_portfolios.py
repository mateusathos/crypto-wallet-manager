"""add icon to portfolios

Revision ID: d8f4a9c2b7e1
Revises: b4d0f9b9d2aa
Create Date: 2026-06-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d8f4a9c2b7e1"
down_revision = "b4d0f9b9d2aa"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("portfolios", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "icon",
                sa.String(length=50),
                nullable=False,
                server_default="wallet",
            )
        )


def downgrade():
    with op.batch_alter_table("portfolios", schema=None) as batch_op:
        batch_op.drop_column("icon")
