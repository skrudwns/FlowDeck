"""add run source and seller in_stock

Revision ID: 8d634bab40ec
Revises: 6f4a3838744e
Create Date: 2026-10-25 02:47:19.790489

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8d634bab40ec"
down_revision: str | Sequence[str] | None = "6f4a3838744e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 자동 생성은 기본값 없는 NOT NULL 컬럼이라 기존 행이 있으면 실패한다.
    # 지금까지의 실행은 모두 다나와라 danawa로 채운 뒤 기본값을 없앤다.
    # 새 실행은 수집기가 값을 넣는다 (ADR-0010)
    op.add_column(
        "collection_runs",
        sa.Column("source", sa.String(length=20), server_default="danawa", nullable=False),
    )
    op.alter_column("collection_runs", "source", server_default=None)
    op.add_column(
        "seller_prices",
        sa.Column("in_stock", sa.Boolean(), server_default="true", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("seller_prices", "in_stock")
    op.drop_column("collection_runs", "source")
