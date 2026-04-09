import sys
from os.path import abspath, dirname
from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlalchemy import pool

from alembic import context

sys.path.insert(0, dirname(dirname(abspath(__file__))))

from database import Base  # noqa: E402
from config import settings  # noqa: E402

# Импортируем все модели, чтобы Alembic их видел
from models.brigade import Brigade, BrigadeMember  # noqa: F401, E402
from models.vehicle import Vehicle  # noqa: F401, E402
from models.request import ServiceRequest  # noqa: F401, E402
from models.route import DailyPlan, RoutePoint, RouteSegment  # noqa: F401, E402

# this is the Alembic Config object
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        settings.DATABASE_URL.replace("sqlite+aiosqlite", "sqlite"),
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
