from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CheckSlotsArgs(StrictToolArgs):
    date: str = Field(description="Clinic-local date in YYYY-MM-DD format.")

    @field_validator("date")
    @classmethod
    def valid_date(cls, value: str) -> str:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError("Use YYYY-MM-DD date format.")
        return value


class BookingArgs(CheckSlotsArgs):
    time: str = Field(description="Clinic-local time in 24-hour HH:MM format.")
    patient_name: str = Field(min_length=1, max_length=100)
    caller_confirmed: bool = Field(
        description="True only after the caller has explicitly confirmed the exact name, date, and time."
    )

    @field_validator("time")
    @classmethod
    def valid_time(cls, value: str) -> str:
        parsed = datetime.strptime(value, "%H:%M").time()
        if parsed.strftime("%H:%M") != value:
            raise ValueError("Use HH:MM 24-hour time format.")
        return value

    @field_validator("patient_name")
    @classmethod
    def safe_name(cls, value: str) -> str:
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("Enter a valid caller-provided name.")
        return value.strip()


class ReferenceArgs(StrictToolArgs):
    reference_code: str = Field(min_length=8, max_length=32)
    patient_name: str = Field(min_length=1, max_length=100)

    @field_validator("reference_code")
    @classmethod
    def normalize_reference(cls, value: str) -> str:
        if any(char.isspace() for char in value):
            raise ValueError("Reference code cannot contain spaces.")
        return value.upper()

    @field_validator("patient_name")
    @classmethod
    def safe_name(cls, value: str) -> str:
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("Enter a valid caller-provided name.")
        return value.strip()


class RescheduleArgs(ReferenceArgs):
    new_date: str
    new_time: str

    @field_validator("new_date")
    @classmethod
    def valid_date(cls, value: str) -> str:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError("Use YYYY-MM-DD date format.")
        return value

    @field_validator("new_time")
    @classmethod
    def valid_time(cls, value: str) -> str:
        parsed = datetime.strptime(value, "%H:%M").time()
        if parsed.strftime("%H:%M") != value:
            raise ValueError("Use HH:MM 24-hour time format.")
        return value


class FAQArgs(StrictToolArgs):
    question: str = Field(min_length=3, max_length=500)


class EscalationArgs(StrictToolArgs):
    category: Literal["emergency", "out_of_scope", "staff_request", "other"]
    brief_reason: str = Field(min_length=1, max_length=120)

    @field_validator("brief_reason")
    @classmethod
    def safe_reason(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value):
            raise ValueError("Use a short plain-text reason.")
        return value.strip()
