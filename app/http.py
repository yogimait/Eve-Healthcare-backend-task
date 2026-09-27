from fastapi.responses import JSONResponse
from pydantic import BaseModel


def _serialize(data):
    if isinstance(data, BaseModel):
        return data.model_dump(mode="json")
    if isinstance(data, dict):
        return {k: _serialize(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [_serialize(v) for v in data]
    return data


def ok(data=None, status_code: int = 200, message: str | None = None) -> JSONResponse:
    body = {"status": True, "statusCode": status_code, "data": _serialize(data)}
    if message is not None:
        body["message"] = message
    return JSONResponse(status_code=status_code, content=body)


def fail(
    code: str,
    message: str,
    details: object = None,
    status_code: int = 400,
) -> JSONResponse:
    error: dict = {"code": code}
    if details is not None:
        error["details"] = details
    body = {
        "status": False,
        "statusCode": status_code,
        "message": message,
        "error": error,
    }
    return JSONResponse(status_code=status_code, content=body)
