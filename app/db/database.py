from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config.settings import settings


def _build_db_url(raw: str) -> str:
    """
    Normalize the DATABASE_URL to use the psycopg3 SQLAlchemy dialect.
    Handles all common URL prefixes:
      postgres://        → postgresql+psycopg://  (Render default)
      postgresql://      → postgresql+psycopg://
      postgresql+psycopg://  → unchanged (already correct)
    """
    if raw.startswith("postgresql+psycopg://"):
        return raw
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg://", 1)
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw


engine = create_engine(
    _build_db_url(settings.DATABASE_URL),
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
