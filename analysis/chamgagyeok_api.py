"""참가격 생필품 가격 정보 Open API(공공데이터포털 15158701)를 받아 캐시한다. AN-0004(#42)에서 쓴다.

- 인증키는 backend/.env의 DATA_GO_KR_KEY. 저장소에 넣지 않는다.
- 응답 XML은 data/external/chamgagyeok/api/에 그대로 저장한다. 같은 요청은 다시 보내지 않는다.
- 개발계정은 상세기능마다 하루 2,000건이다. 실제로 보낸 요청을 날짜별로 세어 1,900건에서 멈춘다.
"""

import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import httpx
from dotenv import load_dotenv

BASE_URL = "https://apis.data.go.kr/B551919/ProductPriceInfoService"
CACHE = Path(__file__).parent / "data" / "external" / "chamgagyeok" / "api"
DAILY_LIMIT = 1900

load_dotenv(Path(__file__).parent.parent / "backend" / ".env")


class QuotaReached(Exception):
    pass


def _count_path() -> Path:
    return CACHE / "calls.json"


def _bump(endpoint: str) -> None:
    path = _count_path()
    counts = json.loads(path.read_text()) if path.exists() else {}
    key = f"{date.today()}:{endpoint}"
    if counts.get(key, 0) >= DAILY_LIMIT:
        raise QuotaReached(key)
    counts[key] = counts.get(key, 0) + 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(counts, indent=1))


def calls_today(endpoint: str) -> int:
    path = _count_path()
    counts = json.loads(path.read_text()) if path.exists() else {}
    return counts.get(f"{date.today()}:{endpoint}", 0)


def fetch(endpoint: str, **params: str) -> str:
    """응답 XML 문자열. 캐시에 있으면 요청하지 않는다."""
    name = "_".join(f"{k}={v}" for k, v in sorted(params.items())) or "all"
    path = CACHE / endpoint / f"{name}.xml"
    if path.exists():
        return path.read_text(encoding="utf-8")
    _bump(endpoint)
    # 상세기능마다 인증키 파라미터 이름이 다르다 (serviceKey / ServiceKey). 둘 다 보낸다
    key = os.environ["DATA_GO_KR_KEY"]
    for attempt in range(3):
        try:
            response = httpx.get(
                f"{BASE_URL}/{endpoint}",
                params={"serviceKey": key, "ServiceKey": key, **params},
                timeout=60,
            )
            break
        except httpx.TransportError:
            if attempt == 2:
                raise
            time.sleep(10)
    response.raise_for_status()
    text = response.text
    code = ET.fromstring(text).findtext("resultCode")
    if code not in ("00", None):
        raise RuntimeError(
            f"{endpoint} {params}: {code} {ET.fromstring(text).findtext('resultMsg')}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    time.sleep(0.2)
    return text


def rows(text: str) -> list[dict[str, str]]:
    """result 아래 항목들을 dict 목록으로."""
    result = ET.fromstring(text).find("result")
    if result is None:
        return []
    return [{c.tag: (c.text or "").strip() for c in item} for item in result]
