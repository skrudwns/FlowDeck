from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session, sessionmaker

from flowdeck.db import make_engine, make_session_factory


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return make_session_factory(make_engine())


def get_session() -> Iterator[Session]:
    # 테스트는 이 함수를 테스트 DB 세션으로 바꿔 끼운다 (tests/conftest.py)
    with get_session_factory()() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
