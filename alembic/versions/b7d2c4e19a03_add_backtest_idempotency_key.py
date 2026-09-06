"""Add backtests.idempotency_key

Revision ID: b7d2c4e19a03
Revises: c961f1f9fde9
Create Date: 2026-09-06 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d2c4e19a03"
down_revision: Union[str, Sequence[str], None] = "c961f1f9fde9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable: existing rows have no key, and submissions that omit the header must stay allowed.
    # The unique constraint is per strategy — Postgres treats NULLs as distinct, so any number of
    # keyless rows coexist while a repeated key on the same strategy is rejected.
    op.add_column("backtests", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        "uq_backtests_strategy_idempotency_key",
        "backtests",
        ["strategy_id", "idempotency_key"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_backtests_strategy_idempotency_key", "backtests", type_="unique")
    op.drop_column("backtests", "idempotency_key")
