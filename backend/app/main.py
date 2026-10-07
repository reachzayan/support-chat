from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.api.articles import router as articles_router
from app.api.auth import router as auth_router
from app.api.canned_replies import router as canned_replies_router
from app.api.conversations import router as conversations_router
from app.api.health import router as health_router
from app.api.internal_dev import router as internal_dev_router
from app.api.kb_sources import router as kb_sources_router
from app.api.knowledge_gaps import router as knowledge_gaps_router
from app.api.logs import router as logs_router
from app.api.notifications import router as notifications_router
from app.api.push_notifications import router as push_notifications_router
from app.api.sites import router as sites_router
from app.api.status import router as status_router
from app.api.visitor_blocks import router as visitor_blocks_router
from app.api.widget_bootstrap import router as widget_bootstrap_router
from app.chat.fanout import start_fanout, stop_fanout
from app.chat.ws_agent import router as agent_ws_router
from app.chat.ws_visitor import router as visitor_ws_router
from app.chat.ws_visitor import stop_bot_generations
from app.db import dispose_engine, session_maker
from app.llm.bot_responder import BotResponder
from app.logging import configure_logging
from app.redis import close_redis
from app.security.surfaces import http_surface_allowed
from app.services.app_log import record_app_log
from app.services.kb_embedder import OpenAIEmbedder
from app.settings import AppEnvironment, get_settings
from app.workers import start_kb_workers, stop_kb_workers


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    await start_fanout()
    if settings.enable_background_workers:
        await start_kb_workers()
    try:
        yield
    finally:
        if settings.enable_background_workers:
            await stop_kb_workers()
        await stop_bot_generations()
        await stop_fanout()
        await close_redis()
        await BotResponder.close_shared_client()
        await OpenAIEmbedder.close_shared_clients()
        await dispose_engine()


async def _persist_unhandled_exception(request: Request, exc: Exception) -> None:
    try:
        async with session_maker()() as session:
            await record_app_log(
                session,
                level="error",
                source="backend",
                logger_name="app.main",
                event="unhandled_exception",
                message=type(exc).__name__,
                detail={
                    "error_class": type(exc).__name__,
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": 500,
                },
            )
            await session.commit()
    except Exception:
        # Logging must never mask the original failure.
        return


def _include_internal_dev_router(application: FastAPI) -> None:
    settings = get_settings()
    if settings.app_env is AppEnvironment.LOCAL and settings.internal_eval_enabled:
        application.include_router(internal_dev_router)


def create_app() -> FastAPI:
    configure_logging()
    application = FastAPI(title="SupportChat", lifespan=lifespan)
    application.include_router(health_router)
    _include_internal_dev_router(application)
    application.include_router(auth_router, prefix="/auth")
    application.include_router(widget_bootstrap_router)
    application.include_router(conversations_router)
    application.include_router(canned_replies_router)
    application.include_router(visitor_blocks_router)
    application.include_router(sites_router)
    application.include_router(articles_router)
    application.include_router(kb_sources_router)
    application.include_router(knowledge_gaps_router)
    application.include_router(logs_router)
    application.include_router(notifications_router)
    application.include_router(push_notifications_router)
    application.include_router(status_router)
    application.include_router(visitor_ws_router)
    application.include_router(agent_ws_router)

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        await _persist_unhandled_exception(request, exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @application.middleware("http")
    async def privacy_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not http_surface_allowed(
            request.url.path,
            request.headers.get("host"),
            get_settings(),
        ):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        try:
            response = await call_next(request)
        except Exception as exc:
            # BaseHTTPMiddleware can surface route exceptions past ExceptionMiddleware
            # under TestClient; persist and convert so failures stay traceable.
            from fastapi import HTTPException
            from fastapi.exceptions import RequestValidationError
            from starlette.exceptions import HTTPException as StarletteHTTPException

            if isinstance(exc, (HTTPException, StarletteHTTPException, RequestValidationError)):
                raise
            await _persist_unhandled_exception(request, exc)
            response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
        path = request.url.path
        if path.startswith(("/auth", "/api/")):
            response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        return response

    return application


app = create_app()
