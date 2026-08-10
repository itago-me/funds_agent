"""MySQL connection helpers for the database migration stage."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import quote_plus, urlsplit, urlunsplit


DEFAULT_MYSQL_HOST = "127.0.0.1"
DEFAULT_MYSQL_PORT = 3306
DEFAULT_MYSQL_DATABASE = "funds_agent"
DEFAULT_MYSQL_USER = "funds_user"
DEFAULT_MYSQL_CHARSET = "utf8mb4"

try:
    from sqlalchemy.orm import DeclarativeBase
except ModuleNotFoundError:
    DeclarativeBase = None  # type: ignore[assignment,misc]


if DeclarativeBase is not None:

    class Base(DeclarativeBase):
        """Base class shared by all SQLAlchemy ORM models."""

else:
    Base = None  # type: ignore[assignment,misc]


@dataclass(frozen=True)
class DatabaseConfig:
    host: str = DEFAULT_MYSQL_HOST
    port: int = DEFAULT_MYSQL_PORT
    database: str = DEFAULT_MYSQL_DATABASE
    user: str = DEFAULT_MYSQL_USER
    password: str = ""
    charset: str = DEFAULT_MYSQL_CHARSET
    database_url: str | None = None


def load_database_config(
    environ: Mapping[str, str] | None = None,
) -> DatabaseConfig:
    _load_project_env()
    env = environ or os.environ
    database_url = env.get("DATABASE_URL")
    if database_url:
        return DatabaseConfig(database_url=database_url)

    return DatabaseConfig(
        host=env.get("MYSQL_HOST", DEFAULT_MYSQL_HOST),
        port=int(env.get("MYSQL_PORT", str(DEFAULT_MYSQL_PORT))),
        database=env.get("MYSQL_DATABASE", DEFAULT_MYSQL_DATABASE),
        user=env.get("MYSQL_USER", DEFAULT_MYSQL_USER),
        password=env.get("MYSQL_PASSWORD", ""),
        charset=env.get("MYSQL_CHARSET", DEFAULT_MYSQL_CHARSET),
    )


@lru_cache(maxsize=1)
def _load_project_env() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return

    cwd = Path.cwd().resolve()
    for directory in (cwd, *cwd.parents):
        env_path = directory / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
            break


def build_database_url(config: DatabaseConfig | None = None) -> str:
    selected_config = config or load_database_config()
    if selected_config.database_url:
        return selected_config.database_url

    user = quote_plus(selected_config.user)
    password = quote_plus(selected_config.password)
    database = quote_plus(selected_config.database)
    return (
        f"mysql+pymysql://{user}:{password}"
        f"@{selected_config.host}:{selected_config.port}/{database}"
        f"?charset={quote_plus(selected_config.charset)}"
    )


def mask_database_url(database_url: str) -> str:
    parts = urlsplit(database_url)
    if not parts.password:
        return database_url

    username = quote_plus(parts.username or "")
    hostname = parts.hostname or ""
    port = f":{parts.port}" if parts.port is not None else ""
    netloc = f"{username}:***@{hostname}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _import_sqlalchemy() -> tuple[Any, Any]:
    try:
        from sqlalchemy import create_engine, text
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "SQLAlchemy/PyMySQL dependencies are not installed. "
            "Run: pip install -r requirements.txt"
        ) from exc
    return create_engine, text


def create_database_engine(database_url: str | None = None) -> Any:
    create_engine, _text = _import_sqlalchemy()
    return create_engine(
        database_url or build_database_url(),
        pool_pre_ping=True,
        future=True,
    )


@lru_cache(maxsize=1)
def get_database_engine() -> Any:
    return create_database_engine()


@lru_cache(maxsize=1)
def get_session_factory() -> Any:
    return create_session_factory(get_database_engine())


def create_session_factory(engine: Any | None = None) -> Any:
    try:
        from sqlalchemy.orm import sessionmaker
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "SQLAlchemy dependencies are not installed. "
            "Run: pip install -r requirements.txt"
        ) from exc

    return sessionmaker(
        bind=engine or create_database_engine(),
        autoflush=False,
        autocommit=False,
        future=True,
    )


def get_db_session() -> Any:
    """Yield one ORM session for a service or FastAPI dependency."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_database_connection(
    database_url: str | None = None,
    engine_factory: Callable[[str], Any] | None = None,
) -> dict[str, str]:
    selected_url = database_url or build_database_url()
    if engine_factory is None:
        _create_engine, text = _import_sqlalchemy()
        statement: Any = text("SELECT 1")
        engine = create_database_engine(selected_url)
    else:
        statement = "SELECT 1"
        engine = engine_factory(selected_url)

    with engine.connect() as connection:
        connection.execute(statement)

    return {
        "status": "ok",
        "database_url": mask_database_url(selected_url),
    }
