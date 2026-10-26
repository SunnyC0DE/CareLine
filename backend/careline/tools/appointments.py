from __future__ import annotations

import secrets
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from backend.careline.config import Settings
from backend.careline.db import ClinicStore
from backend.careline.schemas import BookingArgs, CheckSlotsArgs, ReferenceArgs, RescheduleArgs


_REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class AppointmentTools:
    def __init__(self, store: ClinicStore, settings: Settings):
        self.store = store
        self.settings = settings

    def _now(self) -> datetime:
        return datetime.now(ZoneInfo(self.settings.clinic_timezone))

    def _today(self) -> date:
        return self._now().date()

    def _is_future_slot(self, start_local: str) -> bool:
        local_start = datetime.fromisoformat(start_local).replace(
            tzinfo=ZoneInfo(self.settings.clinic_timezone)
        )
        return local_start > self._now()

    def _make_start(self, day_text: str, time_text: str) -> str:
        day = date.fromisoformat(day_text)
        datetime.strptime(time_text, "%H:%M")
        return f"{day.isoformat()}T{time_text}"

    def check_available_slots(self, raw_date: str) -> dict[str, Any]:
        try:
            args = CheckSlotsArgs(date=raw_date)
        except (ValidationError, ValueError) as exc:
            return {"ok": False, "error": "invalid_date", "message": str(exc)}
        day = date.fromisoformat(args.date)
        if day < self._today():
            return {"ok": False, "error": "invalid_date", "message": "Choose today or a future date."}
        scheduled = self.store.scheduled_slots(day)
        if not scheduled:
            return {"ok": True, "date": args.date, "slots": [], "message": "The clinic has no appointments scheduled on that date."}
        slots = [
            slot[-5:]
            for slot in self.store.available_slots(day)
            if self._is_future_slot(slot)
        ]
        return {"ok": True, "date": args.date, "slots": slots}

    def book_appointment(
        self, raw_date: str, raw_time: str, patient_name: str, caller_confirmed: bool
    ) -> dict[str, Any]:
        try:
            args = BookingArgs(
                date=raw_date,
                time=raw_time,
                patient_name=patient_name,
                caller_confirmed=caller_confirmed,
            )
        except (ValidationError, ValueError) as exc:
            return {"ok": False, "error": "invalid_arguments", "message": str(exc)}
        if not args.caller_confirmed:
            return {
                "ok": False,
                "error": "confirmation_required",
                "message": "Ask the caller to confirm their name, date, and time before booking.",
            }
        day = date.fromisoformat(args.date)
        if day < self._today():
            return {"ok": False, "error": "invalid_date", "message": "Choose today or a future date."}
        start_local = self._make_start(args.date, args.time)
        if start_local not in self.store.scheduled_slots(day):
            return {"ok": False, "error": "invalid_slot", "message": "That time is outside the clinic's appointment schedule."}
        if not self._is_future_slot(start_local):
            return {"ok": False, "error": "invalid_slot", "message": "That appointment time has already passed. Offer a future slot instead."}
        reference = "".join(secrets.choice(_REFERENCE_ALPHABET) for _ in range(8))
        try:
            created = self.store.book(
                patient_name=args.patient_name,
                name_key=self.store.name_key(args.patient_name),
                start_local=start_local,
                reference=reference,
            )
        except Exception:
            return {"ok": False, "error": "storage_error", "message": "The booking could not be saved. Please try again or ask the clinic team to follow up."}
        if not created:
            return {"ok": False, "error": "slot_taken", "message": "That slot is no longer available. Ask the caller to choose another time."}
        return {
            "ok": True,
            "status": "booked",
            "patient_name": args.patient_name,
            "date": args.date,
            "time": args.time,
            "reference_code": reference,
        }

    def reschedule_appointment(
        self, reference_code: str, patient_name: str, new_date: str, new_time: str
    ) -> dict[str, Any]:
        try:
            args = RescheduleArgs(
                reference_code=reference_code,
                patient_name=patient_name,
                new_date=new_date,
                new_time=new_time,
            )
        except (ValidationError, ValueError) as exc:
            return {"ok": False, "error": "invalid_arguments", "message": str(exc)}
        day = date.fromisoformat(args.new_date)
        if day < self._today():
            return {"ok": False, "error": "invalid_date", "message": "Choose today or a future date."}
        start_local = self._make_start(args.new_date, args.new_time)
        if not self._is_future_slot(start_local):
            return {"ok": False, "error": "invalid_slot", "message": "That appointment time has already passed. Offer a future slot instead."}
        try:
            changed, error = self.store.reschedule(
                args.reference_code,
                self.store.name_key(args.patient_name),
                start_local,
            )
        except Exception:
            return {"ok": False, "error": "storage_error", "message": "The reschedule could not be saved. Please ask the clinic team to follow up."}
        if not changed:
            messages = {
                "not_found": "I couldn't verify an active appointment with those details. Ask the caller to check the reference code or request staff follow-up.",
                "invalid_slot": "That time is outside the clinic's appointment schedule. Ask the caller to choose an offered slot.",
                "slot_taken": "That slot is no longer available. Ask the caller to choose another time.",
            }
            return {"ok": False, "error": error or "unknown", "message": messages.get(error, "The reschedule could not be completed.")}
        return {"ok": True, "status": "rescheduled", "date": args.new_date, "time": args.new_time}

    def cancel_appointment(self, reference_code: str, patient_name: str) -> dict[str, Any]:
        try:
            args = ReferenceArgs(reference_code=reference_code, patient_name=patient_name)
        except (ValidationError, ValueError) as exc:
            return {"ok": False, "error": "invalid_arguments", "message": str(exc)}
        try:
            cancelled = self.store.cancel(
                args.reference_code,
                self.store.name_key(args.patient_name),
            )
        except Exception:
            return {"ok": False, "error": "storage_error", "message": "The cancellation could not be saved. Please ask the clinic team to follow up."}
        if not cancelled:
            return {"ok": False, "error": "not_found", "message": "I couldn't verify an active appointment with those details. Ask the caller to check the reference code or request staff follow-up."}
        return {"ok": True, "status": "cancelled"}
