from typing import List

from sqlalchemy import INT, String, Boolean, TEXT, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.database.models import Base
from infrastructure.database.models.base import TimestampMixin, TableNameMixin

NewsStatus = Enum(
    "IN_PROGRESS",
    "APPROVED",
    'DECLINED',
    name="news_status"
)


class Url(Base, TimestampMixin, TableNameMixin):
    url_id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(500))
    check_news: Mapped[bool] = mapped_column(Boolean)
    type_of_feed: Mapped[str] = mapped_column(String(50))


class News(Base, TimestampMixin):
    __tablename__ = 'news'
    # title , body , title_ru, body_ru, source
    news_id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(600))
    body: Mapped[str] = mapped_column(TEXT)
    title_ru: Mapped[str] = mapped_column(String(600))
    body_ru: Mapped[str] = mapped_column(TEXT)
    source: Mapped[str] = mapped_column(String(500))
    source_text: Mapped[str] = mapped_column(TEXT)
    #     slug = Column(String(255), unique=True, index=True, nullable=False)

    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    tags = relationship("Tag", back_populates="news", cascade="all, delete-orphan")
    status: Mapped[str] = mapped_column(NewsStatus, default="IN_PROGRESS", nullable=False)

    check_result: Mapped[List["RelevanceCheckResult"]] = relationship(
        "RelevanceCheckResult",
        back_populates="news",
        cascade="all, delete-orphan",
    )
    messages = relationship("RedactionMessage", back_populates="news")


class RelevanceCheckResult(Base, TimestampMixin, TableNameMixin):
    check_id = mapped_column(INT, primary_key=True, autoincrement=True)
    news_id: Mapped[int] = mapped_column(INT, ForeignKey("news.news_id"), onupdate="CASCADE", nullable=False)
    reason: Mapped[str] = mapped_column(String(600))

    news: Mapped["News"] = relationship(
        "News",
        back_populates="check_result",
    )


class Tag(Base, TableNameMixin):
    tag_id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=False)
    news_id: Mapped[int] = mapped_column(INT, ForeignKey("news.news_id"), onupdate="CASCADE", nullable=True)

    name_ru: Mapped[str] = mapped_column(String(100), unique=False)
    news = relationship("News", back_populates="tags")


class Termin(Base, TableNameMixin):
    termin_id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    original: Mapped[str] = mapped_column(String(100))
    translation: Mapped[str] = mapped_column(String(100))


class RedactionMessage(Base, TableNameMixin):
    redact_id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(INT, unique=True)
    news_id: Mapped[int] = mapped_column(INT, ForeignKey("news.news_id"), onupdate="CASCADE", nullable=True)
    news = relationship("News", back_populates="messages")
