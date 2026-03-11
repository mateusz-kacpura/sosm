"""add_fingerprint_tests

Revision ID: b3f8a2c91d44
Revises: a24f17ea6fe5
Create Date: 2026-03-11 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3f8a2c91d44'
down_revision: Union[str, None] = 'a24f17ea6fe5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('fingerprint_tests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('proxy_url_used', sa.String(), nullable=True),
    sa.Column('results', sa.JSON(), nullable=True),
    sa.Column('error_message', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fingerprint_tests_id'), 'fingerprint_tests', ['id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_fingerprint_tests_id'), table_name='fingerprint_tests')
    op.drop_table('fingerprint_tests')
