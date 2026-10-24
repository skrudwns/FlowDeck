"""uv run uvicorn flowdeck.api.app:app --reload  →  http://localhost:8000/docs"""

from fastapi import FastAPI
from sqlalchemy import text

from flowdeck.api.deps import SessionDep
from flowdeck.api.routes import jobs, products, runs, snapshots


def create_app() -> FastAPI:
    app = FastAPI(
        title="FlowDeck API",
        version="0.1.0",
        description="수집 대상, 가격 이력, 수집 실행 이력 조회 (읽기 전용)",
    )

    @app.get("/health", tags=["health"])
    def health(session: SessionDep) -> dict[str, str]:
        session.execute(text("select 1"))
        return {"status": "ok"}

    app.include_router(jobs.router)
    app.include_router(products.router)
    app.include_router(snapshots.router)
    app.include_router(runs.router)
    return app


app = create_app()
