from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.contest import Contest


class Problem(Base):
    __tablename__ = "problems"

    contest_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contests.contest_id", ondelete="CASCADE"), primary_key=True
    )
    index: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    solved_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    contest: Mapped[Contest] = relationship(back_populates="problems")

    def __repr__(self) -> str:
        return f"<Problem {self.contest_id}{self.index} {self.name}>"
