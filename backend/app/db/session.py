from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
from app.services.memory_manager import Base

settings = get_settings()

connect_args = {}
# Fallback logic to SQLite if postgres is not available
db_url = settings.database_url
if db_url.startswith("postgresql"):
    try:
        import psycopg2
    except ImportError:
        print("Warning: psycopg2 not installed. Falling back to local SQLite database.")
        db_url = "sqlite:///./data/agent_memory.db"

if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(db_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db() -> None:
    # Centrally register all metadata
    # Ensure all models are imported so metadata tracks them
    from app.db.models import Base as DbBase
    from app.services.memory_manager import Base as MemBase
    from app.observability.models import Base as ObsBase
    
    DbBase.metadata.create_all(bind=engine)
    MemBase.metadata.create_all(bind=engine)
    ObsBase.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
