"""add fee column to transactions

Revision ID: b4d0f9b9d2aa
Revises: f1a2b3c4d5e6
Create Date: 2026-04-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b4d0f9b9d2aa"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column_names = {column["name"] for column in inspector.get_columns("transactions")}

    if "fee" not in column_names:
        with op.batch_alter_table("transactions", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "fee",
                    sa.Numeric(precision=18, scale=8),
                    nullable=False,
                    server_default="0",
                )
            )
        with op.batch_alter_table("transactions", schema=None) as batch_op:
            batch_op.alter_column("fee", server_default=None)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column_names = {column["name"] for column in inspector.get_columns("transactions")}

    if "fee" in column_names:
        with op.batch_alter_table("transactions", schema=None) as batch_op:
            batch_op.drop_column("fee")
