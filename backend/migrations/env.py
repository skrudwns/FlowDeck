"""Alembic 실행 환경.

DB 주소는 alembic.ini가 아니라 flowdeck 설정(.env 또는 환경 변수 DATABASE_URL)에서 읽는다.
로컬과 Neon에 같은 마이그레이션을 적용하기 위해서다.
"""

from logging.config import fileConfig

from alembic import context

from flowdeck.config import get_settings
from flowdeck.db import make_engine, sqlalchemy_url
from flowdeck.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """DB에 접속하지 않고 SQL만 출력한다 (alembic upgrade --sql)."""
    url = sqlalchemy_url(get_settings().database_url.get_secret_value())
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine()

    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
