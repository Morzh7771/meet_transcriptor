"""empty message

Revision ID: 513b353942ef
Revises: 169144015cdf
Create Date: 2025-09-30 15:25:21.191137

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '513b353942ef'
down_revision: Union[str, Sequence[str], None] = '169144015cdf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('meet', sa.Column('next_meet_scenario', sa.Text(), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('meet', 'next_meet_scenario')