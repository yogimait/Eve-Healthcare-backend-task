import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.background import PROCESSED, RETRY, _finalize_event, process_event
from app.config import settings
from app.database import get_db
from app.errors import app_error
from app.http import ok
from app.models import (
    EVENT_FAILED,
    EVENT_PERMANENTLY_FAILED,
    EVENT_PROCESSED,
    WebhookEvent,
)
from app.schemas import WebhookPayload

router = APIRouter(tags=["webhooks"])


def _validation_details(exc: ValidationError) -> list[dict]:
    return [
        {"field": ".".join(str(loc) for loc in err["loc"] if loc != "body"), "reason": err["msg"]}
        for err in exc.errors()
    ]


def _ack(event: WebhookEvent) -> dict:
    if event.status == EVENT_PROCESSED:
        return {"event_id": event.event_id, "processed": False, "reason": "ALREADY_PROCESSED"}
    reason = {
        EVENT_FAILED: "QUEUED_FOR_RETRY",
        EVENT_PERMANENTLY_FAILED: event.last_error or "PERMANENTLY_FAILED",
    }.get(event.status, "PROCESSING")
    return {"event_id": event.event_id, "processed": False, "reason": reason}


@router.post("/payments/webhook")
async def payment_webhook(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")
    expected = hmac.new(settings.webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        raise app_error("WEBHOOK_INVALID_SIGNATURE", "Invalid webhook signature")

    try:
        payload = WebhookPayload.model_validate_json(raw)
    except ValidationError as exc:
        raise app_error("VALIDATION_ERROR", "Invalid webhook payload", details=_validation_details(exc))

    existing = db.get(WebhookEvent, payload.event_id)
    if existing is not None:
        return ok(_ack(existing))

    event = WebhookEvent(
        event_id=payload.event_id,
        payment_id=payload.payment_id,
        payload=json.loads(raw),
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(WebhookEvent, payload.event_id)
        return ok(_ack(existing))

    try:
        result, reason = process_event(db, event)
    except Exception as exc:
        db.rollback()
        result, reason = RETRY, type(exc).__name__
    _finalize_event(db, event, result, reason)

    data: dict = {"event_id": event.event_id, "processed": result == PROCESSED}
    if result != PROCESSED:
        data["reason"] = reason or event.status
    return ok(data)
