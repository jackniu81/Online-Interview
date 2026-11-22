"""SQLAlchemy ORM models (design D3)."""
import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class GradingStatus(str, enum.Enum):
    UNANSWERED = "unanswered"
    PENDING = "pending"
    GRADING = "grading"
    GRADED = "graded"
    FAILED = "failed"


class ResultStatus(str, enum.Enum):
    EXCELLENT = "excellent"
    PASS = "pass"
    FAIL = "fail"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(Text)  # Markdown, may contain code blocks
    reference_answer: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    candidate_name: Mapped[str | None] = mapped_column(String(100))
    candidate_phone: Mapped[str | None] = mapped_column(String(30))
    question_count: Mapped[int] = mapped_column(Integer)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_score: Mapped[int | None] = mapped_column(Integer)
    result_status: Mapped[str | None] = mapped_column(String(20))  # ResultStatus
    recording_path: Mapped[str | None] = mapped_column(String(500))

    questions: Mapped[list["ExamQuestion"]] = relationship(
        back_populates="exam", cascade="all, delete-orphan", order_by="ExamQuestion.sort_order"
    )
    answers: Mapped[list["ExamAnswer"]] = relationship(
        back_populates="exam", cascade="all, delete-orphan", order_by="ExamAnswer.sort_order"
    )
    events: Mapped[list["ProctoringEvent"]] = relationship(
        back_populates="exam", cascade="all, delete-orphan", order_by="ProctoringEvent.occurred_at"
    )


class ExamQuestion(Base):
    """Frozen snapshot of a question at exam creation time."""

    __tablename__ = "exam_questions"
    __table_args__ = (UniqueConstraint("exam_id", "sort_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer)  # 0-based
    question_content: Mapped[str] = mapped_column(Text)
    reference_answer: Mapped[str] = mapped_column(Text)

    exam: Mapped[Exam] = relationship(back_populates="questions")


class ExamAnswer(Base):
    """Pre-created row per question; answer + AI grading result."""

    __tablename__ = "exam_answers"
    __table_args__ = (UniqueConstraint("exam_id", "sort_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer)
    answer_text: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[int | None] = mapped_column(Integer)  # 0-100
    feedback: Mapped[str | None] = mapped_column(Text)
    grading_status: Mapped[str] = mapped_column(
        String(20), default=GradingStatus.UNANSWERED.value
    )

    exam: Mapped[Exam] = relationship(back_populates="answers")


class ProctoringEvent(Base):
    __tablename__ = "proctoring_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    exam: Mapped[Exam] = relationship(back_populates="events")
