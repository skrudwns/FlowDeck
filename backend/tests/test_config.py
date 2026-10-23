import pytest
from pydantic import ValidationError

from flowdeck.config import Settings


def test_reads_values_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5433/db")
    monkeypatch.setenv("NAVER_CLIENT_ID", "client-id")
    monkeypatch.setenv("NAVER_CLIENT_SECRET", "client-secret")

    settings = Settings(_env_file=None)

    assert settings.database_url.get_secret_value() == "postgresql://u:p@localhost:5433/db"
    assert settings.naver_client_id == "client-id"
    assert settings.naver_client_secret.get_secret_value() == "client-secret"


def test_naver_keys_are_optional(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5433/db")
    monkeypatch.delenv("NAVER_CLIENT_ID", raising=False)
    monkeypatch.delenv("NAVER_CLIENT_SECRET", raising=False)

    settings = Settings(_env_file=None)

    assert settings.naver_client_id is None
    assert settings.naver_client_secret is None


def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_secrets_are_hidden_in_repr(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:password123@localhost:5433/db")
    monkeypatch.setenv("NAVER_CLIENT_SECRET", "client-secret")

    text = repr(Settings(_env_file=None))

    assert "password123" not in text
    assert "client-secret" not in text
