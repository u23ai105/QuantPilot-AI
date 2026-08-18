import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class EvalQuestion(Base):
    __tablename__ = "eval_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    question_text: Mapped[str] = mapped_column(String, nullable=False)
    expected_answer: Mapped[str] = mapped_column(String, nullable=False)
    expected_document_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    expected_page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    runs = relationship("EvalRun", back_populates="question", cascade="all, delete-orphan")


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[int] = mapped_column(ForeignKey("eval_questions.id"), nullable=False, index=True)

    retrieval_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    citation_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    canonical_format_hit: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)
    answer_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    generated_answer: Mapped[str] = mapped_column(String, nullable=True)
    retrieved_sources_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    question = relationship("EvalQuestion", back_populates="runs")
