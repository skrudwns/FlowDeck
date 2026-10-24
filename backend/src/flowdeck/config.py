"""환경 변수에서 설정을 읽는다.

로컬은 backend/.env, GitHub Actions는 저장소 Secrets에서 들어온다.
.env에 더 이상 쓰지 않는 값이 남아 있어도 무시한다 (extra="ignore").
"""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: SecretStr


@lru_cache
def get_settings() -> Settings:
    return Settings()
