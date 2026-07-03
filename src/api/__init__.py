from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from config.settings import get_settings
    from observability.events import configure_logging
    from db.session import init_db

    configure_logging(get_settings().log_level)
    init_db()
    yield


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            error = {"code": detail["code"], "message": detail.get("message", "")}
        else:
            error = {"code": "http_error", "message": str(detail)}
        return JSONResponse(status_code=exc.status_code, content={"data": None, "error": error})

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "data": None,
                "error": {"code": "validation_error", "message": str(exc.errors())},
            },
        )


def create_app() -> FastAPI:
    app = FastAPI(title="Ledger Lens", version="1.0.0", lifespan=_lifespan)

    from api import health, datasets
    app.include_router(health.router)
    app.include_router(datasets.router)

    _register_error_handlers(app)

    # Serve the built Next.js static export at /app
    # Run `cd frontend && pnpm build` to generate frontend/out/ before starting.
    # Server starts fine without it (API-only mode when out/ doesn't exist).
    frontend_out = Path(__file__).resolve().parent.parent.parent / "frontend" / "out"
    if frontend_out.exists():
        app.mount("/app", StaticFiles(directory=str(frontend_out), html=True), name="frontend")

    return app


app = create_app()
