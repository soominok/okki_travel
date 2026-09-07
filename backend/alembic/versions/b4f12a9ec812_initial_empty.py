"""initial empty

Revision ID: b4f12a9ec812
Revises:
Create Date: 2026-09-01 15:37:13.574489

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "b4f12a9ec812"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
