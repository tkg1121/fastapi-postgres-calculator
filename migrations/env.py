"""Alembic configuration using the same connection settings as FastAPI."""

from logging.config import fileConfig

from alembic import context

from app.database import get_database_url, get_engine
from app.models import Base


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    """Keep autogeneration scoped to the application-owned schema."""
    if type_ == "schema":
        return name == "calculator"
    return True


if context.is_offline_mode():
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    with get_engine().connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()
