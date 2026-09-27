import random

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.background import schedule_provider_event
from app.database import get_db
from app.deps import get_current_user
from app.errors import app_error
from app.http import ok
from app.models import (
    BOOKING_CONFIRMED,
    BOOKING_FAILED,
    BOOKING_PENDING,
    Booking,
    PAYMENT_FAILED,
    PAYMENT_PENDING,
    PAYMENT_SUCCESS,
    Payment,
    User,
)
from app.rate_limit import rate_limited
from app.schemas import PaymentCreate, PaymentOut, PaymentResultOut

router = APIRouter(tags=["payments"])


@router.post("/payments", dependencies=[Depends(rate_limited("payments"))])
def create_payment(
    body: PaymentCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = db.get(Booking, body.booking_id)
    if booking is None:
        raise app_error("BOOKING_NOT_FOUND", f"Booking {body.booking_id} does not exist")
    if booking.user_id != user.id and not user.is_admin:
        raise app_error("BOOKING_NOT_OWNED", "You do not have access to this booking")
    if booking.status != BOOKING_PENDING:
        raise app_error(
            "BOOKING_NOT_PENDING",
            f"Booking in status {booking.status} cannot be paid",
            details={"current_status": booking.status},
        )
    in_progress = db.scalar(
        select(Payment).where(Payment.booking_id == booking.id, Payment.status == PAYMENT_PENDING)
    )
    if in_progress is not None:
        raise app_error(
            "PAYMENT_ALREADY_IN_PROGRESS",
            "A payment for this booking is already in progress",
        )

    status = body.force_status or random.choice([PAYMENT_SUCCESS, PAYMENT_FAILED])
    payment = Payment(booking_id=booking.id, amount_paise=booking.amount_paise, status=PAYMENT_PENDING)
    db.add(payment)
    db.commit()

    if body.mode == "webhook":
        background_tasks.add_task(schedule_provider_event, payment.id, status)
        return ok(PaymentOut.model_validate(payment), 201)

    payment.status = status
    booking.status = BOOKING_CONFIRMED if status == PAYMENT_SUCCESS else BOOKING_FAILED
    db.commit()
    result = PaymentResultOut(
        payment_id=payment.id,
        booking_id=booking.id,
        amount=booking.amount,
        status=status,
        booking_status=booking.status,
    )
    return ok(result, 201)


@router.get("/payments/{payment_id}")
def get_payment(payment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise app_error("PAYMENT_NOT_FOUND", f"Payment {payment_id} does not exist")
    booking = payment.booking
    if booking.user_id != user.id and not user.is_admin:
        raise app_error("BOOKING_NOT_OWNED", "You do not have access to this payment")
    return ok(PaymentOut.model_validate(payment))
