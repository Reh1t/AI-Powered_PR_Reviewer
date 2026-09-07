"""Add vector extension and embeddings table

Revision ID: 7971b19c163d
Revises: b27d03da090b
Create Date: 2026-09-07 18:14:32.494825

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7971b19c163d'
down_revision: Union[str, Sequence[str], None] = 'b27d03da090b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')


def downgrade() -> None:
    """Downgrade schema."""
    op.execute('DROP EXTENSION IF EXISTS vector')
