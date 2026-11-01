# analysis

분석 노트(`docs/analysis/AN-NNNN`)와 짝이 되는 코드. 파일 하나가 노트 하나다.

파일은 `# %%`로 셀을 나눈 파이썬 스크립트다. 터미널에서 그대로 돌릴 수 있고, VS Code나 Jupyter(jupytext)에서 노트북처럼 셀 단위로 열 수 있다. 노트북(.ipynb)은 출력이 파일에 섞여 변경 내역을 읽기 어려워서 쓰지 않는다.

## 데이터

```bash
uv sync
uv run python export.py        # Neon에서 받아 data/에 저장 (backend/.env.neon 필요)
uv run python an0001.py        # 표는 터미널에, 그래프는 docs/assets/에
```

- `data/`는 커밋하지 않는다. 다나와에서 모은 원본은 공개하지 않는다 (ADR-0004 수집 원칙 6). 분석 결과(집계, 그래프)만 기록에 남긴다.
- `export.py`는 DB를 읽기만 한다.
