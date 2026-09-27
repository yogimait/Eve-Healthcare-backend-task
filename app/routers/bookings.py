from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.errors import app_error
from app.http import ok
from app.models import (
    ACTIVE_BOOKING_STATUSES,
    BOOKING_CANCELLED,
    BOOKING_CONFIRMED,
    BOOKING_PENDING,
    Booking,
    Centre,
    CentreTest,
    DiagnosticTest,
    Payment,
    PAYMENT_PENDING,
    User,
)
from app.schemas import BookingCreate, BookingOut
from app.util import to_utc_naive, utcnow

router = APIRouter(tags=["bookings"])


def _get_owned_booking(booking_id: int, user: User, db: Session) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise app_error("BOOKING_NOT_FOUND", f"Booking {booking_id} does not exist")
    if booking.user_id != user.id and not user.is_admin:
        raise app_error("BOOKING_NOT_OWNED", "You do not have access to this booking")
    return booking


@router.post("/bookings")
def create_booking(body: BookingCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    centre = db.get(Centre, body.centre_id)
    if centre is None:
        raise app_error("CENTRE_NOT_FOUND", f"Centre {body.centre_id} does not exist")
    test = db.get(DiagnosticTest, body.test_id)
    if test is None:
        raise app_error("TEST_NOT_FOUND", f"Test {body.test_id} does not exist")

    centre_test = db.scalar(
        select(CentreTest).where(CentreTest.centre_id == body.centre_id, CentreTest.test_id == body.test_id)
    )
    if centre_test is None:
        raise app_error(
            "TEST_NOT_AVAILABLE",
            f"Centre {body.centre_id} does not offer test {body.test_id}",
            details={"centre_id": body.centre_id, "test_id": body.test_id},
        )

    appointment = to_utc_naive(body.appointment)
    if appointment <= utcnow():
        raise app_error(
            "INVALID_APPOINTMENT",
            "Appointment must be in the future",
            details={"appointment": body.appointment.isoformat()},
        )

    # ponytail: row lock only on Postgres; SQLite is single-writer so no lock needed
    use_row_lock = db.bind.dialect.name == "postgresql"
    db.get(Centre, body.centre_id, with_for_update=use_row_lock)

    slot_taken = db.scalar(
        select(Booking)
        .join(Booking.centre_test)
        .where(
            CentreTest.centre_id == body.centre_id,
            Booking.appointment == appointment,
            Booking.status.in_(ACTIVE_BOOKING_STATUSES),
        )
    )
    if slot_taken is not None:
        raise app_error(
            "SLOT_UNAVAILABLE",
            "This appointment slot is already booked at this centre",
            details={"centre_id": body.centre_id, "appointment": body.appointment.isoformat()},
        )

    booking = Booking(
        user_id=user.id,
        centre_test_id=centre_test.id,
        appointment=appointment,
        amount_paise=centre_test.price_paise,
        status=BOOKING_PENDING,
    )
    db.add(booking)
    db.commit()
    return ok(BookingOut.model_validate(booking), 201)


@router.get("/bookings")
def list_bookings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bookings = db.scalars(
        select(Booking).where(Booking.user_id == user.id).order_by(Booking.id.desc())
    ).all()
    items = [BookingOut.model_validate(b) for b in bookings]
    return ok({"items": items, "total": len(items)})


@router.get("/bookings/{booking_id}")
def get_booking(booking_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    booking = _get_owned_booking(booking_id, user, db)
    return ok(BookingOut.model_validate(booking))


@router.post("/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    booking = _get_owned_booking(booking_id, user, db)
    if booking.status not in (BOOKING_PENDING, BOOKING_CONFIRMED):
        raise app_error(
            "INVALID_STATE_TRANSITION",
            f"Booking in status {booking.status} cannot be cancelled",
            details={"current_status": booking.status},
        )
    pending_payment = db.scalar(
        select(Payment).where(Payment.booking_id == booking.id, Payment.status == PAYMENT_PENDING)
    )
    if pending_payment is not None:
        raise app_error(
            "PAYMENT_ALREADY_IN_PROGRESS",
            "Cannot cancel a booking while its payment is in progress",
        )
    booking.status = BOOKING_CANCELLED
    db.commit()
    return ok(BookingOut.model_validate(booking))
