"""add_background_style_to_groups

Revision ID: f4a8c3d71e52
Revises: 937e2b3ae0a9
Create Date: 2026-03-12 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4a8c3d71e52'
down_revision: Union[str, None] = '937e2b3ae0a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('groups', sa.Column('background_style', sa.String(), nullable=True))

def downgrade() -> None:
    op.drop_column('groups', 'background_style')
