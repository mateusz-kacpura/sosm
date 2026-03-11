"""rename_adspower_to_browser_profile_id

Revision ID: d5a3b7e29f81
Revises: c7d2e4f18a63
Create Date: 2026-03-11 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd5a3b7e29f81'
down_revision: Union[str, None] = 'c7d2e4f18a63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.alter_column('accounts', 'adspower_profile_id',
                    new_column_name='browser_profile_id')

def downgrade() -> None:
    op.alter_column('accounts', 'browser_profile_id',
                    new_column_name='adspower_profile_id')
