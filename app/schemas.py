from datetime import datetime
from decimal import Decimal
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    is_admin: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class CentreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    location: str = Field(min_length=1, max_length=160)


class TestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)


class CentreTestCreate(BaseModel):
    test_id: int = Field(gt=0)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class CentreTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    test_id: int
    name: str
    description: str
    price: float


class CentreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str
    tests: list[CentreTestOut]


class TestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str


class BookingCreate(BaseModel):
    centre_id: int = Field(gt=0)
    test_id: int = Field(gt=0)
    appointment: datetime


BookingStatus = Literal["PENDING", "CONFIRMED", "FAILED", "CANCELLED"]


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    centre_id: int
    test_id: int
    centre_name: str
    test_name: str
    appointment: datetime
    amount: float
    status: BookingStatus
    created_at: datetime

    @field_serializer("appointment", "created_at")
    def serialize_dt(self, value: datetime | None) -> str | None:
        return value.isoformat() + "Z" if value else None


class PaymentCreate(BaseModel):
    booking_id: int = Field(gt=0)
    force_status: Literal["SUCCESS", "FAILED"] | None = None
    mode: Literal["direct", "webhook"] = "direct"


PaymentStatus = Literal["PENDING", "SUCCESS", "FAILED"]


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int
    amount: float
    status: PaymentStatus
    provider_reference: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_dt(self, value: datetime | None) -> str | None:
        return value.isoformat() + "Z" if value else None


class PaymentResultOut(BaseModel):
    payment_id: int
    booking_id: int
    amount: float
    status: PaymentStatus
    booking_status: BookingStatus


class WebhookPayload(BaseModel):
    event_id: str = Field(min_length=1, max_length=64)
    payment_id: int = Field(gt=0)
    status: Literal["SUCCESS", "FAILED"]
    amount: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
