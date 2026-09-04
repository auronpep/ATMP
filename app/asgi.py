"""Application implementation - ASGI."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.config import config
from app.models.exception import HttpException
from app.router import root_api_router
from app.utils import utils


def exception_handler(request: Request, e: HttpException):
    return JSONResponse(
        status_code=e.status_code,
        content=utils.get_response(e.status_code, e.data, e.message),
    )


def validation_exception_handler(request: Request, e: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content=utils.get_response(
            status=400, data=e.errors(), message="field required"
        ),
    )


@asynccontextmanager
async def lifespan(instance: FastAPI):
    """Startup/shutdown hooks.

    `@app.on_event` is deprecated in FastAPI and emits a DeprecationWarning on
    the pinned 0.136.3; lifespan handlers are the supported replacement.
    """
    logger.info("startup event")
    yield
    logger.info("shutdown event")


def get_application() -> FastAPI:
    """Initialize FastAPI application.

    Returns:
       FastAPI: Application object instance.

    """
    instance = FastAPI(
        title=config.project_name,
        description=config.project_description,
        version=config.project_version,
        debug=False,
        lifespan=lifespan,
    )
    instance.include_router(root_api_router)
    instance.add_exception_handler(HttpException, exception_handler)
    instance.add_exception_handler(RequestValidationError, validation_exception_handler)
    return instance


app = get_application()


def resolve_cors_settings(raw_allowed_origins: str) -> tuple[list[str], bool]:
    """Resolve (allow_origins, allow_credentials) from CORS_ALLOWED_ORIGINS.

    `allow_origins=["*"]` together with `allow_credentials=True` does NOT send a
    literal `*`. Starlette echoes back whichever Origin the caller sent and adds
    `Access-Control-Allow-Credentials: true`, so any website a user visits could
    drive this API with their cookies and read the responses. Credentials are
    therefore only enabled when an explicit allowlist is configured.
    """
    origins = [origin.strip() for origin in raw_allowed_origins.split(",") if origin.strip()]
    if origins:
        return origins, True
    return ["*"], False


# Configures the CORS middleware for the FastAPI app
cors_allowed_origins, cors_allow_credentials = resolve_cors_settings(
    os.getenv("CORS_ALLOWED_ORIGINS", "")
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins,
    allow_credentials=cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

task_dir = utils.task_dir()
app.mount(
    "/tasks", StaticFiles(directory=task_dir, html=True, follow_symlink=True), name=""
)

public_dir = utils.public_dir()
app.mount("/", StaticFiles(directory=public_dir, html=True), name="")
