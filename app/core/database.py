# app/core/database.py

from sqlmodel import SQLModel, create_engine
from typing import Generator
import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Session

load_dotenv()

# Get database URL from environment variable, default to SQLite
DATABASE_URL = os.getenv(
    "DATABASE_URL", "sqlite:///./pdf_assistant.db"  # Default SQLite database file
)

# Create database engine
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True to see SQL queries
    connect_args={"check_same_thread": False},  # Needed for SQLite
)


def init_db() -> None:
    """Initialize the database, creating all tables."""
    SQLModel.metadata.create_all(engine)


def get_db() -> Generator:
    """Get database session."""
    with Session(engine) as session:
        yield session


@asynccontextmanager
async def get_async_session():
    """Get async database session."""
    # For SQLite, we'll use the sync session since SQLite doesn't support async operations
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
