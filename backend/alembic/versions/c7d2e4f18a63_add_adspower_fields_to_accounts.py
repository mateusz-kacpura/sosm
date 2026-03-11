"""add_adspower_fields_to_accounts

Revision ID: c7d2e4f18a63
Revises: b3f8a2c91d44
Create Date: 2026-03-11 18:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d2e4f18a63'
down_revision: Union[str, None] = 'b3f8a2c91d44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('accounts', sa.Column('adspower_profile_id', sa.String(), nullable=True))
    op.add_column('accounts', sa.Column('session_cookies_backup', sa.JSON(), nullable=True))

def downgrade() -> None:
    op.drop_column('accounts', 'session_cookies_backup')
    op.drop_column('accounts', 'adspower_profile_id')
