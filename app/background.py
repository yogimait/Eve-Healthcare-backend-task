import asyncio
import logging
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import SessionLocal
from app.models import (
    BOOKING_CONFIRMED,
    BOOKING_FAILED,
    EVENT_FAILED,
    EVENT_PERMANENTLY_FAILED,
    EVENT_PROCESSED,
    PAYMENT_PENDING,
    PAYMENT_SUCCESS,
    Booking,
    Payment,
    WebhookEvent,
)
from app.util import to_paise, utcnow

logger = logging.getLogger("eve.webhook")

RETRY = "retry"
PROCESSED = "processed"
PERMANENT = "permanent"

_retry_loop_task: asyncio.Task | None = None
_provider_tasks: set[asyncio.Task] = set()


def process_event(db, event: WebhookEvent) -> tuple[str, str | None]:
    payment = db.get(Payment, event.payment_id)
    if payment is None:
        return RETRY, "PAYMENT_NOT_FOUND"
    if payment.status != PAYMENT_PENDING:
        if payment.status == event.payload.get("status"):
            return PROCESSED, None
        return PERMANENT, "CONFLICTING_STATUS"
    amount = event.payload.get("amount")
    if amount is not None and to_paise(amount) != payment.amount_paise:
        return PERMANENT, "AMOUNT_MISMATCH"
    status = event.payload.get("status")
    payment.status = status
    booking = db.get(Booking, payment.booking_id)
    booking.status = BOOKING_CONFIRMED if status == PAYMENT_SUCCESS else BOOKING_FAILED
    return PROCESSED, None


def _finalize_event(db, event: WebhookEvent, result: str, reason: str | None) -> None:
    event.attempts += 1
    if result == PROCESSED:
        event.status = EVENT_PROCESSED
        event.last_error = None
        event.next_retry_at = None
    elif result == PERMANENT:
        event.status = EVENT_PERMANENTLY_FAILED
        event.last_error = reason
        event.next_retry_at = None
    elif event.attempts >= settings.retry_max_attempts:
        event.status = EVENT_PERMANENTLY_FAILED
        event.last_error = reason
        event.next_retry_at = None
    else:
        event.status = EVENT_FAILED
        event.last_error = reason
        backoff = settings.retry_base_backoff_seconds * (2 ** (event.attempts - 1))
        event.next_retry_at = utcnow() + timedelta(seconds=backoff)
    db.commit()


def deliver_event(payment_id: int, status: str) -> str:
    with SessionLocal() as db:
        event = WebhookEvent(
            event_id=f"evt_{uuid4().hex}",
            payment_id=payment_id,
            payload={"event_id": None, "payment_id": payment_id, "status": status},
            status="PENDING",
        )
        event.payload["event_id"] = event.event_id
        db.add(event)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return "duplicate"
        try:
            result, reason = process_event(db, event)
        except Exception as exc:
            db.rollback()
            result, reason = RETRY, type(exc).__name__
        _finalize_event(db, event, result, reason)
        return result


async def _simulate_provider(payment_id: int, status: str) -> None:
    await asyncio.sleep(settings.simulated_provider_delay_seconds)
    await asyncio.to_thread(deliver_event, payment_id, status)


async def schedule_provider_event(payment_id: int, status: str) -> None:
    task = asyncio.create_task(_simulate_provider(payment_id, status))
    _provider_tasks.add(task)
    task.add_done_callback(_provider_tasks.discard)


def process_due_events() -> int:
    now = utcnow()
    processed = 0
    with SessionLocal() as db:
        events = db.scalars(
            select(WebhookEvent).where(
                WebhookEvent.status == EVENT_FAILED,
                WebhookEvent.next_retry_at.is_not(None),
                WebhookEvent.next_retry_at <= now,
            )
        ).all()
        for event in events:
            try:
                result, reason = process_event(db, event)
            except Exception as exc:
                db.rollback()
                result, reason = RETRY, type(exc).__name__
            _finalize_event(db, event, result, reason)
            if result == PROCESSED:
                processed += 1
    return processed


async def retry_loop() -> None:
    while True:
        await asyncio.sleep(settings.retry_interval_seconds)
        try:
            count = await asyncio.to_thread(process_due_events)
            if count:
                logger.info("webhook retry processed %d event(s)", count)
        except Exception:
            logger.exception("webhook retry loop failed")


def start_retry_loop() -> None:
    global _retry_loop_task
    _retry_loop_task = asyncio.create_task(retry_loop())


def stop_retry_loop() -> None:
    if _retry_loop_task is not None:
        _retry_loop_task.cancel()
