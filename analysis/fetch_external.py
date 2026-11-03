"""분석 검증용 외부 데이터를 data/external/에 받는다. 선정 이유는 docs/adr/0013, 목록은 datasets.md.

uv run python fetch_external.py            # 전부
uv run python fetch_external.py kosis      # 하나만. 이름은 아래 FETCHERS

- 받은 파일은 커밋하지 않는다. 데이터마다 재배포 조건이 달라서 저장소에는 목록과 이 스크립트만 둔다.
- 저장소는 커밋을 고정해서 받는다. 같은 버전으로 다시 받을 수 있다.
- 다른 저장소의 스크립트(TCPD의 build_tcpd.py 등)는 실행하지 않는다.
- 공공데이터포털은 사이트의 다운로드 횟수 확인을 그대로 거친다. 보안문자를 요구하면 멈춘다.
"""

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

EXTERNAL = Path(__file__).parent / "data" / "external"

TCPD_COMMIT = "e8f19a3635e3b7f1a8aff59ce7f4d9bea17525c0"
TCPDBENCH_COMMIT = "167210005c09d2c44f9b2083b95f989a64be4b6b"

# 공공데이터포털 파일은 달마다 새 파일로 바뀐다. 이번에 쓴 판을 적어 둔다
CHAMGAGYEOK = {
    "page": "https://www.data.go.kr/data/15083256/fileData.do",
    "public_data_pk": "15083256",
    "detail_pk": "uddi:4f684682-d8a2-446e-be30-adfffdaae05a",
    "file": "price_20260925.csv",
    "sha256": "23258dcebb605a515c9e10ed2d09f1ed064cee08428aa2f080005db430d24c7d",
}

KOSIS_CPI = {"table": "DT_1J22001", "start": "202410", "end": "202610"}


def git(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True)


def fetch_tcpd() -> None:
    dest = EXTERNAL / "tcpd"
    if not dest.exists():
        dest.mkdir(parents=True)
        git("init", "-q", cwd=dest)
        git(
            "remote", "add", "origin", "https://github.com/alan-turing-institute/TCPD.git", cwd=dest
        )
    git("fetch", "-q", "--depth", "1", "origin", TCPD_COMMIT, cwd=dest)
    git("checkout", "-q", "FETCH_HEAD", cwd=dest)
    print(f"tcpd: {TCPD_COMMIT[:7]} → {dest}")


def fetch_tcpdbench() -> None:
    """135MB 저장소에서 결과 폴더(analysis/output)만 받는다."""
    dest = EXTERNAL / "tcpdbench"
    if not dest.exists():
        git(
            "clone", "-q", "--filter=blob:none", "--no-checkout",
            "https://github.com/alan-turing-institute/TCPDBench.git", str(dest),
        )  # fmt: skip
        git("sparse-checkout", "set", "analysis/output", cwd=dest)
    git("fetch", "-q", "origin", TCPDBENCH_COMMIT, cwd=dest)
    git("checkout", "-q", TCPDBENCH_COMMIT, cwd=dest)
    print(f"tcpdbench: {TCPDBENCH_COMMIT[:7]} analysis/output → {dest}")


def fetch_chamgagyeok() -> None:
    dest = EXTERNAL / "chamgagyeok" / CHAMGAGYEOK["file"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    base = "https://www.data.go.kr"
    headers = {"Referer": CHAMGAGYEOK["page"], "X-Requested-With": "XMLHttpRequest"}
    with httpx.Client(timeout=60, follow_redirects=True) as http:
        http.get(CHAMGAGYEOK["page"]).raise_for_status()
        meta = http.post(
            f"{base}/tcs/dss/selectFileDataDownload.do",
            headers=headers,
            data={
                "publicDataDetailPk": CHAMGAGYEOK["detail_pk"],
                "publicDataPk": CHAMGAGYEOK["public_data_pk"],
                "atchFileId": "",
                "fileDetailSn": "1",
                "publicDataTyCode": "PR0051",
            },
        ).json()
        info = meta["dataSetFileDetailInfo"]
        file_id, sn = meta["atchFileId"], meta["fileDetailSn"]
        limit = http.post(
            f"{base}/cmm/cmm/check-limit.json",
            headers=headers,
            data={"atchFileId": file_id, "fileDetailSn": sn},
        ).json()
        if limit.get("needCaptcha"):
            raise SystemExit("공공데이터포털이 보안문자를 요구해서 멈춤. 브라우저에서 직접 받는다")
        response = http.get(
            f"{base}/cmm/cmm/fileDownload.do",
            params={"atchFileId": file_id, "fileDetailSn": sn, "dataNm": info["dataNm"]},
            headers={"Referer": CHAMGAGYEOK["page"]},
        )
        response.raise_for_status()
    digest = hashlib.sha256(response.content).hexdigest()
    if digest != CHAMGAGYEOK["sha256"]:
        # 새 달 파일로 바뀌었을 수 있다. 덮어쓰지 않고 이름을 따로 둔다
        dest = dest.with_name(f"price_{info['dataNm'].rsplit('_', 1)[-1]}.csv")
        print(f"chamgagyeok: 기록한 판과 해시가 다름 ({info['dataNm']}). datasets.md를 고친다")
    dest.write_bytes(response.content)
    print(f"chamgagyeok: {info['dataNm']} {len(response.content):,}바이트 → {dest}")


def fetch_kosis() -> None:
    """통계청 지출목적별 소비자물가지수(품목 포함), 전국 월별. 키는 backend/.env의 KOSIS_API_KEY"""
    load_dotenv(Path(__file__).parent.parent / "backend" / ".env")
    start, end = KOSIS_CPI["start"], KOSIS_CPI["end"]
    dest = EXTERNAL / "kosis" / f"{KOSIS_CPI['table']}_{start}_{end}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    response = httpx.get(
        "https://kosis.kr/openapi/Param/statisticsParameterData.do",
        params={
            "method": "getList",
            "apiKey": os.environ["KOSIS_API_KEY"],
            "orgId": "101",
            "tblId": KOSIS_CPI["table"],
            "itmId": "T ",
            "objL1": "T10",  # 전국
            "objL2": "ALL",  # 지출목적별 품목 전부
            "prdSe": "M",
            "startPrdDe": start,
            "endPrdDe": end,
            "format": "json",
            "jsonVD": "Y",
        },
        timeout=180,
    )
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict):
        raise SystemExit(f"kosis: {data}")
    dest.write_text(response.text, encoding="utf-8")
    print(f"kosis: {len(data):,}칸 → {dest}")


def check_cavallo() -> None:
    """openICPSR는 로그인과 약관 동의를 거쳐 직접 받는다. 받은 위치만 확인한다"""
    raw = EXTERNAL / "cavallo2017" / "REPLICATION" / "RAWDATA" / "online_offline_ALL_clean.dta"
    if not raw.exists():
        raise SystemExit(f"cavallo2017: {raw}가 없음. datasets.md의 받는 방법을 따른다")
    print(f"cavallo2017: {raw.stat().st_size:,}바이트 확인")


FETCHERS = {
    "tcpd": fetch_tcpd,
    "tcpdbench": fetch_tcpdbench,
    "chamgagyeok": fetch_chamgagyeok,
    "kosis": fetch_kosis,
    "cavallo2017": check_cavallo,
}


def main(names: list[str]) -> None:
    for name in names or FETCHERS:
        FETCHERS[name]()


if __name__ == "__main__":
    main(sys.argv[1:])
