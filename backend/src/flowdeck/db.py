"""DB 연결."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from flowdeck.config import get_settings


def sqlalchemy_url(raw: str) -> str:
    """Neon과 .env의 postgresql:// 주소를 psycopg 3 드라이버 주소로 바꾼다.

    접두어 없이 쓰면 SQLAlchemy는 psycopg2를 찾는데, 설치한 건 psycopg 3이다.
    """
    for prefix in ("postgresql://", "postgres://"):
        if raw.startswith(prefix):
            return "postgresql+psycopg://" + raw.removeprefix(prefix)
    return raw


def make_engine(url: str | None = None) -> Engine:
    if url is None:
        url = get_settings().database_url.get_secret_value()
    # Neon은 쉬고 있던 연결을 끊을 수 있어서 쓰기 전에 확인한다
    return create_engine(sqlalchemy_url(url), pool_pre_ping=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
