from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from app.core.config import get_settings

settings = get_settings()

_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )
else:
    # Postgres (Supabase etc). Serverless functions spin up/tear down
    # frequently, so:
    #   - pool_pre_ping: discard dead connections instead of handing them
    #     back out (a connection opened by a previous, now-frozen
    #     invocation looks "open" but the socket is gone).
    #   - NullPool: don't hold a persistent connection pool across
    #     invocations -- open a fresh connection per request and close it
    #     after. Pairs with Supabase's "Transaction" pooler connection
    #     string (port 6543, pgbouncer) rather than the direct connection
    #     (port 5432), which only allows a handful of concurrent clients.
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        poolclass=NullPool,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()