from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contest_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    problem_index: Mapped[str | None] = mapped_column(String(8), nullable=True)
    problem_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    problem_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    problem_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)
    programming_language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    submission_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="submissions")

    def __repr__(self) -> str:
        return f"<Submission {self.id} user={self.user_id} verdict={self.verdict}>"
