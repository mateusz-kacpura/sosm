"""add_account_fanpage_discovery_fields

Revision ID: f344f462fc7d
Revises: 229b3ebe66a5
Create Date: 2026-03-18 17:14:20.555246

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f344f462fc7d'
down_revision: Union[str, None] = '229b3ebe66a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('accounts', sa.Column('fanpage_discovery_status', sa.String(), nullable=True))
    op.add_column('accounts', sa.Column('fanpage_discovery_error', sa.String(), nullable=True))

def downgrade() -> None:
    op.drop_column('accounts', 'fanpage_discovery_error')
    op.drop_column('accounts', 'fanpage_discovery_status')
