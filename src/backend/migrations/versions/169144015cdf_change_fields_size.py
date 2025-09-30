"""change fields size

Revision ID: 169144015cdf
Revises: 
Create Date: 2025-09-29 17:41:28.161196

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '169144015cdf'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('client_education', 'field_of_study',
        existing_type=sa.String(length=50),
        type_=sa.String(length=100),
        existing_nullable=False)

    op.alter_column('client_education', 'degree',
        existing_type=sa.String(length=50),
        type_=sa.String(length=100),
        existing_nullable=False)

    op.alter_column('client_education', 'university_name',
        existing_type=sa.String(length=50),
        type_=sa.String(length=100),
        existing_nullable=False)

    op.alter_column('client_employment', 'company_name',
        existing_type=sa.String(length=50),
        type_=sa.String(length=100),
        existing_nullable=False)

    op.alter_column('client_employment', 'job_title',
        existing_type=sa.String(length=50),
        type_=sa.String(length=100),
        existing_nullable=False)



def downgrade() -> None:
    op.alter_column('client_employment', 'job_title',
        existing_type=sa.String(length=100),
        type_=sa.String(length=50),
        existing_nullable=False)

    op.alter_column('client_employment', 'company_name',
        existing_type=sa.String(length=100),
        type_=sa.String(length=50),
        existing_nullable=False)

    op.alter_column('client_education', 'university_name',
        existing_type=sa.String(length=100),
        type_=sa.String(length=50),
        existing_nullable=False)

    op.alter_column('client_education', 'degree',
        existing_type=sa.String(length=100),
        type_=sa.String(length=50),
        existing_nullable=False)

    op.alter_column('client_education', 'field_of_study',
        existing_type=sa.String(length=100),
        type_=sa.String(length=50),
        existing_nullable=False)

