"""
Database connection management for FireWatch AI
Supports PostgreSQL with PostGIS extension
"""

import os
import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError

from .models import Base

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """
    Database connection manager with connection pooling.

    Supports PostgreSQL with PostGIS for geospatial queries.
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30
    ):
        """
        Initialize database connection.

        Args:
            database_url: PostgreSQL connection URL
            pool_size: Connection pool size
            max_overflow: Max connections beyond pool_size
            pool_timeout: Timeout for getting connection from pool
        """
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://firewatch:firewatch@localhost:5432/firewatch_db"
        )

        # Create engine with connection pooling
        self.engine = create_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,  # Verify connections before use
            echo=os.getenv("DB_ECHO", "false").lower() == "true"
        )

        # Session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        logger.info(f"Database connection initialized: {self._mask_url(self.database_url)}")

    def _mask_url(self, url: str) -> str:
        """Mask password in connection URL for logging."""
        if "@" in url and ":" in url:
            parts = url.split("@")
            credentials = parts[0].split(":")
            if len(credentials) >= 3:
                credentials[-1] = "****"
            return ":".join(credentials) + "@" + parts[1]
        return url

    def create_tables(self) -> None:
        """Create all database tables."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except SQLAlchemyError as e:
            logger.error(f"Failed to create tables: {e}")
            raise

    def drop_tables(self) -> None:
        """Drop all database tables. Use with caution!"""
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.warning("All database tables dropped")
        except SQLAlchemyError as e:
            logger.error(f"Failed to drop tables: {e}")
            raise

    def check_connection(self) -> bool:
        """
        Check if database connection is healthy.

        Returns:
            True if connection is healthy
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError as e:
            logger.error(f"Database connection check failed: {e}")
            return False

    def check_postgis(self) -> bool:
        """
        Check if PostGIS extension is available.

        Returns:
            True if PostGIS is installed
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT PostGIS_Version()"))
                version = result.scalar()
                logger.info(f"PostGIS version: {version}")
                return True
        except SQLAlchemyError:
            logger.warning("PostGIS extension not available")
            return False

    def enable_postgis(self) -> bool:
        """
        Enable PostGIS extension if not already enabled.

        Returns:
            True if PostGIS is enabled
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
                conn.commit()
            logger.info("PostGIS extension enabled")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to enable PostGIS: {e}")
            return False

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions.

        Yields:
            SQLAlchemy session
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def close(self) -> None:
        """Close database connection and dispose engine."""
        self.engine.dispose()
        logger.info("Database connection closed")


# Global database instance
_db: Optional[DatabaseConnection] = None


def get_db() -> DatabaseConnection:
    """
    Get global database connection instance.

    Returns:
        DatabaseConnection instance
    """
    global _db
    if _db is None:
        _db = DatabaseConnection()
    return _db


def init_db(database_url: Optional[str] = None) -> DatabaseConnection:
    """
    Initialize global database connection.

    Args:
        database_url: Optional database URL override

    Returns:
        DatabaseConnection instance
    """
    global _db
    _db = DatabaseConnection(database_url=database_url)
    return _db


def get_session() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI to get database session.

    Yields:
        SQLAlchemy session
    """
    db = get_db()
    session = db.SessionLocal()
    try:
        yield session
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()
