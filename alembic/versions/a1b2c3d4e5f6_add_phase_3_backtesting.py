"""Add Phase 3 backtesting models

Revision ID: a1b2c3d4e5f6
Revises: abae3ec9059f
Create Date: 2026-08-18 10:56:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "abae3ec9059f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # strategies table
    op.create_table(
        "strategies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("rules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_strategy_user_name"),
    )
    op.create_index(op.f("ix_strategies_user_id"), "strategies", ["user_id"], unique=False)

    # backtests table
    op.create_table(
        "backtests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("strategy_id", sa.Integer(), nullable=False),
        sa.Column("ticker_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("initial_capital", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("commission", sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column("slippage", sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticker_id"], ["tickers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("start_date < end_date", name="chk_backtests_dates"),
        sa.CheckConstraint("initial_capital > 0", name="chk_backtests_capital"),
        sa.CheckConstraint("commission >= 0", name="chk_backtests_commission"),
        sa.CheckConstraint("slippage >= 0", name="chk_backtests_slippage"),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED')",
            name="chk_backtests_status",
        ),
    )
    op.create_index(op.f("ix_backtests_strategy_id"), "backtests", ["strategy_id"], unique=False)
    op.create_index(op.f("ix_backtests_status"), "backtests", ["status"], unique=False)

    # backtest_results table
    op.create_table(
        "backtest_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("backtest_id", sa.Integer(), nullable=False),
        sa.Column("total_return", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("cagr", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("volatility", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("sharpe_ratio", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("sortino_ratio", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("win_rate", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("total_trades", sa.Integer(), nullable=False),
        sa.Column("equity_curve_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("trades_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["backtest_id"], ["backtests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("backtest_id", name="uq_backtest_results_backtest_id"),
    )


def downgrade() -> None:
    op.drop_table("backtest_results")
    op.drop_index(op.f("ix_backtests_status"), table_name="backtests")
    op.drop_index(op.f("ix_backtests_strategy_id"), table_name="backtests")
    op.drop_table("backtests")
    op.drop_index(op.f("ix_strategies_user_id"), table_name="strategies")
    op.drop_table("strategies")
