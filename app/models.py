from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.util import from_paise, utcnow

BOOKING_PENDING = "PENDING"
BOOKING_CONFIRMED = "CONFIRMED"
BOOKING_FAILED = "FAILED"
BOOKING_CANCELLED = "CANCELLED"
ACTIVE_BOOKING_STATUSES = (BOOKING_PENDING, BOOKING_CONFIRMED)

PAYMENT_PENDING = "PENDING"
PAYMENT_SUCCESS = "SUCCESS"
PAYMENT_FAILED = "FAILED"

EVENT_PENDING = "PENDING"
EVENT_PROCESSED = "PROCESSED"
EVENT_FAILED = "FAILED"
EVENT_PERMANENTLY_FAILED = "PERMANENTLY_FAILED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DiagnosticTest(Base):
    __tablename__ = "tests"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(500), default="")

    centre_tests: Mapped[list["CentreTest"]] = relationship(back_populates="test")


class Centre(Base):
    __tablename__ = "centres"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    location: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    tests: Mapped[list["CentreTest"]] = relationship(
        back_populates="centre", cascade="all, delete-orphan"
    )


class CentreTest(Base):
    __tablename__ = "centre_tests"
    __table_args__ = (UniqueConstraint("centre_id", "test_id", name="uq_centre_test"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"), index=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id"), index=True)
    price_paise: Mapped[int] = mapped_column(Integer)

    centre: Mapped[Centre] = relationship(back_populates="tests")
    test: Mapped[DiagnosticTest] = relationship(back_populates="centre_tests")

    @property
    def name(self) -> str:
        return self.test.name

    @property
    def description(self) -> str:
        return self.test.description

    @property
    def price(self) -> float:
        return from_paise(self.price_paise)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    centre_test_id: Mapped[int] = mapped_column(ForeignKey("centre_tests.id"), index=True)
    appointment: Mapped[datetime] = mapped_column(DateTime, index=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default=BOOKING_PENDING, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship()
    centre_test: Mapped[CentreTest] = relationship()

    @property
    def centre_id(self) -> int:
        return self.centre_test.centre_id

    @property
    def test_id(self) -> int:
        return self.centre_test.test_id

    @property
    def centre_name(self) -> str:
        return self.centre_test.centre.name

    @property
    def test_name(self) -> str:
        return self.centre_test.test.name

    @property
    def amount(self) -> float:
        return from_paise(self.amount_paise)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), index=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default=PAYMENT_PENDING, index=True)
    provider_reference: Mapped[str] = mapped_column(String(64), unique=True, default=lambda: uuid4().hex)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    booking: Mapped[Booking] = relationship()

    @property
    def amount(self) -> float:
        return from_paise(self.amount_paise)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), default=EVENT_PENDING, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
