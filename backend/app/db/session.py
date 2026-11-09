import logging
from typing import Generator, Optional, Any, Dict
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from app.core.config import DATABASE_URL

logger = logging.getLogger(__name__)

Base = declarative_base()


def normalize_database_url(url: str) -> str:
    """
    Normalize database connection URLs according to the installed database driver (psycopg2).
    Cloud providers like Neon and Render often emit postgres:// or generic postgresql://,
    which in SQLAlchemy 2.0 attempts to load psycopg (v3) unless explicitly mapped to psycopg2.
    Normalizes postgres:// and postgresql:// -> postgresql+psycopg2://.
    """
    if not url:
        return url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def create_configured_engine(url: Optional[str] = None) -> Engine:
    """
    Create a SQLAlchemy Engine with driver-appropriate connection pooling and settings.
    - For SQLite: check_same_thread disabled.
    - For PostgreSQL / Neon: pool_pre_ping enabled to detect disconnected serverless sessions,
      pool_recycle set to 300s to discard stale connections, with bounded pool sizes.
    """
    raw_url = url or DATABASE_URL
    normalized_url = normalize_database_url(raw_url)

    engine_kwargs: Dict[str, Any] = {}
    if normalized_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # PostgreSQL / Neon pooling settings
        engine_kwargs.update({
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_size": 10,
            "max_overflow": 20,
        })

    return create_engine(normalized_url, **engine_kwargs)


engine = create_configured_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(target_engine: Optional[Engine] = None) -> None:
    """
    Initialize database schema, handling extension registration and migration/startup errors explicitly.
    - Creates pgvector 'vector' extension on PostgreSQL if supported and required by the model.
    - Executes Base.metadata.create_all to ensure all tables exist.
    """
    eng = target_engine or engine
    dialect_name = eng.dialect.name
    logger.info("Initializing database schema on dialect: %s", dialect_name)

    if dialect_name == "postgresql":
        # Check if pgvector is supported by the installed environment and required by models
        try:
            from app.db.models import HAS_PGVECTOR
        except ImportError:
            HAS_PGVECTOR = False

        if HAS_PGVECTOR:
            try:
                with eng.connect() as conn:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                    conn.commit()
                logger.info("PostgreSQL pgvector extension verified or created successfully.")
            except Exception as ext_err:
                logger.warning(
                    "Unable to create or verify PostgreSQL 'vector' extension (%s). "
                    "Ensure pgvector is enabled in your PostgreSQL instance if vector columns are needed.",
                    ext_err
                )
        else:
            logger.info("pgvector library not installed; skipping pgvector extension creation.")

    try:
        Base.metadata.create_all(bind=eng)
        logger.info("Database schema initialized successfully.")
    except Exception as db_err:
        logger.error("Failed to initialize database tables: %s", db_err, exc_info=True)
        raise RuntimeError(f"Database schema initialization failed: {db_err}") from db_err


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
