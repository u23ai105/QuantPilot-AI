from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Backtest(Base):
    __tablename__ = "backtests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(Integer, ForeignKey("strategies.id", ondelete="CASCADE"), index=True, nullable=False)
    ticker_id: Mapped[int] = mapped_column(Integer, ForeignKey("tickers.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    initial_capital: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=10000.00)
    commission: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.001)
    slippage: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.000)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED", index=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    result: Mapped["BacktestResult"] = relationship("BacktestResult", back_populates="backtest", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("start_date < end_date", name="chk_backtests_dates"),
        CheckConstraint("initial_capital > 0", name="chk_backtests_capital"),
        CheckConstraint("commission >= 0", name="chk_backtests_commission"),
        CheckConstraint("slippage >= 0", name="chk_backtests_slippage"),
        CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED')",
            name="chk_backtests_status",
        ),
    )


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("backtests.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    total_return: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    cagr: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    volatility: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    sortino_ratio: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    max_drawdown: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    win_rate: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False)

    equity_curve_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    trades_json: Mapped[list] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    backtest: Mapped["Backtest"] = relationship("Backtest", back_populates="result")
