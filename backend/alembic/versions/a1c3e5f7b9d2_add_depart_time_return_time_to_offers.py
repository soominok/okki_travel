"""add depart_time and return_time to offers

Revision ID: a1c3e5f7b9d2
Revises: 383dcf6b47f1
Create Date: 2026-09-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c3e5f7b9d2"
down_revision: str | None = "8e15245760f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("offers", sa.Column("depart_time", sa.Time(), nullable=True))
    op.add_column("offers", sa.Column("return_time", sa.Time(), nullable=True))


def downgrade() -> None:
    op.drop_column("offers", "return_time")
    op.drop_column("offers", "depart_time")
