import pytest
from pydantic import ValidationError

from flowdeck.config import Settings


def test_reads_database_url_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5433/db")

    settings = Settings(_env_file=None)

    assert settings.database_url.get_secret_value() == "postgresql://u:p@localhost:5433/db"


def test_ignores_values_no_longer_used(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5433/db")
    monkeypatch.setenv("NAVER_CLIENT_ID", "old-value")

    Settings(_env_file=None)


def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_database_url_is_hidden_in_repr(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:password123@localhost:5433/db")

    assert "password123" not in repr(Settings(_env_file=None))
