from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from .config import get_config

config = get_config()

connect_args = {"check_same_thread": False} if "sqlite" in config.database.url else {}
engine = create_engine(config.database.url, echo=False, connect_args=connect_args)


def init_db():
    # Import models to register them with SQLModel metadata

    # Ensure the database directory exists for SQLite
    from .config import get_config

    cfg = get_config()
    if "sqlite" in cfg.database.url:
        import re

        # Extract file path from sqlite:///path
        match = re.search(r"sqlite:///(.+)", cfg.database.url)
        if match:
            from pathlib import Path

            db_path = Path(match.group(1))
            db_path.parent.mkdir(parents=True, exist_ok=True)

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
