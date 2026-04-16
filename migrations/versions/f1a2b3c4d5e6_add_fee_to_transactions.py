"""add fee to transactions

Revision ID: f1a2b3c4d5e6
Revises: a36d3719e4ed
Create Date: 2026-01-14

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'a36d3719e4ed'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No operation: fee column intentionally not added
    pass


def downgrade() -> None:
    # No operation: schema unchanged
    pass
