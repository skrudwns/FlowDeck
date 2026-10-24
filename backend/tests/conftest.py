import os

import pytest
from sqlalchemy.exc import OperationalError

from flowdeck.db import make_engine, make_session_factory
from flowdeck.models import Base

# 개발 DB(flowdeck)와 분리된 테스트 전용 DB. compose.yaml의 Postgres에 만들어 둔다.
DEFAULT_TEST_DATABASE_URL = "postgresql://flowdeck:flowdeck@localhost:5433/flowdeck_test"


@pytest.fixture
def session_factory():
    engine = make_engine(os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL))
    try:
        engine.connect().close()
    except OperationalError:
        pytest.skip("테스트 DB에 연결할 수 없음 (docker compose up -d 필요)")

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield make_session_factory(engine)
    Base.metadata.drop_all(engine)
    engine.dispose()
