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

    # Healthchecks.io 체크 주소 (ADR-0007). 없으면 신호를 보내지 않는다.
    # 주소를 알면 누구나 가짜 신호를 보낼 수 있어서 비밀 값으로 다룬다.
    healthcheck_url: SecretStr | None = None
    # 연습 쇼핑몰 수집 체크 (ADR-0010). 다나와와 따로 둔다
    mockshop_healthcheck_url: SecretStr | None = None

    # 포털에서 수집 워크플로를 바로 실행할 때 쓴다 (ADR-0011). 없으면 다음 정기 호출 때 실행된다.
    # Actions가 자동으로 주는 GITHUB_TOKEN과 헷갈리지 않게 이름을 따로 둔다
    portal_github_token: SecretStr | None = None
    github_repository: str = "skrudwns/FlowDeck"
    collect_workflow: str = "collect.yml"
    github_ref: str = "main"


@lru_cache
def get_settings() -> Settings:
    return Settings()
