"""환경 변수에서 설정을 읽는다.

로컬은 backend/.env, GitHub Actions는 저장소 Secrets에서 들어온다.
"""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: SecretStr

    # 키 없이도 DB 작업은 할 수 있게 비워 둘 수 있다. 수집기에서 확인한다.
    naver_client_id: str | None = None
    naver_client_secret: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
