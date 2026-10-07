"""Database configuration and session lifecycle."""

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = "sqlite:///./chatbot.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


def create_db_and_tables() -> None:
    """Create tables that do not already exist."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Provide one database session per request."""
    with Session(engine) as session:
        yield session

