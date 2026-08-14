from logging.config import fileConfig
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.models.base import Base
import app.models  # noqa: F401 - registers all mapped tables

config = context.config
database_url = str(settings.database_url).replace("postgresql+asyncpg", "postgresql+psycopg")
parsed_url = urlsplit(database_url)
query = dict(parse_qsl(parsed_url.query, keep_blank_values=True))
if query.get("ssl") == "require":
    query["sslmode"] = query.pop("ssl")
query.pop("statement_cache_size", None)
database_url = urlunsplit(parsed_url._replace(query=urlencode(query)))
config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
