import pytest

from flowdeck.db import sqlalchemy_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "postgresql://u:p@localhost:5433/flowdeck",
            "postgresql+psycopg://u:p@localhost:5433/flowdeck",
        ),
        (
            "postgres://u:p@host.neon.tech/flowdeck?sslmode=require",
            "postgresql+psycopg://u:p@host.neon.tech/flowdeck?sslmode=require",
        ),
        (
            "postgresql+psycopg://u:p@localhost:5433/flowdeck",
            "postgresql+psycopg://u:p@localhost:5433/flowdeck",
        ),
    ],
)
def test_sqlalchemy_url_uses_psycopg3_driver(raw, expected):
    assert sqlalchemy_url(raw) == expected
