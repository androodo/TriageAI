# Alembic migrations for TriageAI

from logging.config import fileConfig

from alembic import context

# Import Base and all models so Alembic can detect them via metadata
from app.models.base import Base
from app.models.ci_run import CIRun  # noqa: F401
from app.models.failure_log import FailureLog  # noqa: F401
from app.models.triage_result import TriageResult  # noqa: F401
from app.models.issue_draft import IssueDraft  # noqa: F401
from app.config import settings

config = context.config

# Override sqlalchemy.url from alembic.ini with the env var value
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    from sqlalchemy import engine_from_config, pool
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()