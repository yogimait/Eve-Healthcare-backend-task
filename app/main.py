import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.background import start_retry_loop, stop_retry_loop
from app.config import settings
from app.database import Base, engine
from app.errors import AppError
from app.http import fail, ok
from app.routers import auth, bookings, centres, payments, webhooks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

HTTP_ERROR_CODES = {
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    429: "RATE_LIMITED",
}


def _validation_details(exc: RequestValidationError) -> list[dict]:
    return [
        {"field": ".".join(str(loc) for loc in err["loc"] if loc != "body"), "reason": err["msg"]}
        for err in exc.errors()
    ]


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    if settings.retry_loop_enabled:
        start_retry_loop()
    yield
    stop_retry_loop()


app = FastAPI(title="EVE Healthcare Backend", version="1.0.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(centres.admin_router)
app.include_router(bookings.router)
app.include_router(payments.router)
app.include_router(webhooks.router)


@app.get("/health", tags=["health"])
def health():
    return ok({"service": "eve-backend", "status": "running"})


@app.exception_handler(AppError)
def app_error_handler(_: Request, exc: AppError):
    return fail(exc.code, exc.message, exc.details, exc.status_code)


@app.exception_handler(RequestValidationError)
def validation_error_handler(_: Request, exc: RequestValidationError):
    return fail("VALIDATION_ERROR", "Request validation failed", _validation_details(exc), 422)


@app.exception_handler(StarletteHTTPException)
def http_error_handler(_: Request, exc: StarletteHTTPException):
    code = HTTP_ERROR_CODES.get(exc.status_code, "HTTP_ERROR")
    return fail(code, str(exc.detail), None, exc.status_code)


@app.exception_handler(Exception)
def unhandled_error_handler(_: Request, exc: Exception):
    logging.getLogger("eve.app").exception("Unhandled error: %s", exc)
    return fail("INTERNAL_ERROR", "Internal server error", None, 500)
