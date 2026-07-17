"""
Database models and connection management.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, Boolean, Integer, ForeignKey
from datetime import datetime
from typing import Optional, List
from .config import settings


# Create async engine
engine = create_async_engine(settings.database_url, echo=settings.debug)

# Session factory
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Novel(Base):
    """Novel model."""
    __tablename__ = "novels"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    cover_url: Mapped[Optional[str]] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(100))  # Source channel
    source_id: Mapped[Optional[str]] = mapped_column(String(100))  # Original ID from source
    status: Mapped[str] = mapped_column(String(50), default="ongoing")  # ongoing, completed, etc.
    chapters_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    # chapters: Mapped[List["Chapter"]] = relationship(back_populates="novel")


class Chapter(Base):
    """Chapter model."""
    __tablename__ = "chapters"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(Integer, ForeignKey("novels.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, default=0)
    source_url: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    # novel: Mapped["Novel"] = relationship(back_populates="chapters")


class SourceRule(Base):
    """Website scraping rule model."""
    __tablename__ = "source_rules"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100))
    rules_json: Mapped[str] = mapped_column(Text)  # JSON string containing scraping rules
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(50), default="manual")  # manual, ai
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Ranking(Base):
    """Ranking list model."""
    __tablename__ = "rankings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g., "月票榜", "推荐票榜"
    source: Mapped[str] = mapped_column(String(100))  # Source platform
    type: Mapped[str] = mapped_column(String(50))  # daily, weekly, monthly, all_time
    novels: Mapped[str] = mapped_column(Text)  # JSON array of novel IDs in order
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


async def get_db() -> AsyncSession:
    """Get database session."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
