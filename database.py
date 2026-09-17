from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from services.config import settings


class Base(DeclarativeBase):
    pass


engine_options: dict = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    engine_options["connect_args"] = {
        "check_same_thread": False,
        "timeout": settings.sqlite_timeout,
    }

engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute(f"PRAGMA busy_timeout = {int(settings.sqlite_timeout * 1000)}")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
