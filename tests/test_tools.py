from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.careline.config import Settings
from backend.careline.db import ClinicStore
from backend.careline.tools.appointments import AppointmentTools
from backend.careline.tools.clinic_info import retrieve_clinic_info
from backend.careline.tools.escalation import record_escalation


def next_workday(settings: Settings, offset: int = 1) -> date:
    cursor = datetime.now(ZoneInfo(settings.clinic_timezone)).date()
    count = 0
    while count < offset:
        cursor += timedelta(days=1)
        if cursor.weekday() in settings.working_days:
            count += 1
    return cursor


def test_slots_skip_lunch_and_closed_weekday(store: ClinicStore, settings: Settings) -> None:
    day = next_workday(settings)
    slots = store.scheduled_slots(day)
    assert "09:00" in [slot[-5:] for slot in slots]
    assert "12:00" not in [slot[-5:] for slot in slots]
    assert "12:30" not in [slot[-5:] for slot in slots]
    assert "13:00" in [slot[-5:] for slot in slots]
    weekend = day
    while weekend.weekday() not in {5, 6}:
        weekend += timedelta(days=1)
    assert store.scheduled_slots(weekend) == []


def test_booking_requires_explicit_confirmation(store: ClinicStore, settings: Settings) -> None:
    tools = AppointmentTools(store, settings)
    result = tools.book_appointment(next_workday(settings).isoformat(), "09:00", "Test Person", False)
    assert result == {
        "ok": False,
        "error": "confirmation_required",
        "message": "Ask the caller to confirm their name, date, and time before booking.",
    }


def test_booking_and_slot_conflict(store: ClinicStore, settings: Settings) -> None:
    tools = AppointmentTools(store, settings)
    day = next_workday(settings).isoformat()
    first = tools.book_appointment(day, "09:00", "First Person", True)
    second = tools.book_appointment(day, "09:00", "Second Person", True)
    assert first["ok"] is True
    assert len(first["reference_code"]) == 8
    assert second["ok"] is False
    assert second["error"] == "slot_taken"
    assert "09:00" not in tools.check_available_slots(day)["slots"]


def test_invalid_and_past_dates_are_rejected(store: ClinicStore, settings: Settings) -> None:
    tools = AppointmentTools(store, settings)
    invalid = tools.check_available_slots("2027-02-30")
    past_day = datetime.now(ZoneInfo(settings.clinic_timezone)).date() - timedelta(days=1)
    past = tools.check_available_slots(past_day.isoformat())
    assert invalid["ok"] is False and invalid["error"] == "invalid_date"
    assert past["ok"] is False and past["error"] == "invalid_date"


def test_same_day_past_slots_are_not_offered_booked_or_rescheduled(
    store: ClinicStore, settings: Settings, monkeypatch
) -> None:
    tools = AppointmentTools(store, settings)
    target = next_workday(settings)
    clinic_now = datetime.combine(
        target,
        datetime.strptime("15:30", "%H:%M").time(),
        tzinfo=ZoneInfo(settings.clinic_timezone),
    )
    monkeypatch.setattr(tools, "_now", lambda: clinic_now)

    available = tools.check_available_slots(target.isoformat())
    assert "09:00" not in available["slots"]
    assert "15:30" not in available["slots"]
    assert "16:00" in available["slots"]

    past_booking = tools.book_appointment(
        target.isoformat(), "09:00", "Past Person", True
    )
    assert past_booking["error"] == "invalid_slot"

    future_booking = tools.book_appointment(
        target.isoformat(), "16:00", "Future Person", True
    )
    assert future_booking["ok"] is True
    past_reschedule = tools.reschedule_appointment(
        future_booking["reference_code"],
        "Future Person",
        target.isoformat(),
        "09:00",
    )
    assert past_reschedule["error"] == "invalid_slot"


def test_invalid_time_format_is_recoverable(store: ClinicStore, settings: Settings) -> None:
    result = AppointmentTools(store, settings).book_appointment(
        next_workday(settings).isoformat(), "nine-ish", "Test Person", True
    )
    assert result["ok"] is False
    assert result["error"] == "invalid_arguments"


def test_lunch_time_is_not_a_bookable_slot(store: ClinicStore, settings: Settings) -> None:
    result = AppointmentTools(store, settings).book_appointment(
        next_workday(settings).isoformat(), "12:00", "Test Person", True
    )
    assert result["ok"] is False
    assert result["error"] == "invalid_slot"


def test_reschedule_success_requires_reference_and_name(store: ClinicStore, settings: Settings) -> None:
    tools = AppointmentTools(store, settings)
    original = next_workday(settings).isoformat()
    target = next_workday(settings, 2).isoformat()
    booked = tools.book_appointment(original, "09:00", "Schedule Person", True)
    moved = tools.reschedule_appointment(
        booked["reference_code"], "  SCHEDULE   PERSON ", target, "10:00"
    )
    wrong_owner = tools.reschedule_appointment(
        booked["reference_code"], "Another Person", original, "10:00"
    )
    assert moved["ok"] is True
    assert moved["status"] == "rescheduled"
    assert wrong_owner["ok"] is False
    assert wrong_owner["error"] == "not_found"


def test_reschedule_conflict_does_not_move_appointment(store: ClinicStore, settings: Settings) -> None:
    tools = AppointmentTools(store, settings)
    day_one = next_workday(settings).isoformat()
    day_two = next_workday(settings, 2).isoformat()
    mover = tools.book_appointment(day_one, "09:00", "Mover Person", True)
    _occupied = tools.book_appointment(day_two, "09:00", "Existing Person", True)
    result = tools.reschedule_appointment(
        mover["reference_code"], "Mover Person", day_two, "09:00"
    )
    assert result["ok"] is False
    assert result["error"] == "slot_taken"
    assert "09:00" not in tools.check_available_slots(day_one)["slots"]


def test_cancel_is_authorized_idempotent_and_case_insensitive(
    store: ClinicStore, settings: Settings
) -> None:
    tools = AppointmentTools(store, settings)
    booked = tools.book_appointment(
        next_workday(settings).isoformat(), "09:00", "Cancel Person", True
    )
    assert tools.cancel_appointment(booked["reference_code"], " CANCEL   PERSON ")["status"] == "cancelled"
    second = tools.cancel_appointment(booked["reference_code"], "Cancel Person")
    wrong_name = tools.cancel_appointment(booked["reference_code"], "Different Person")
    assert second["error"] == "not_found"
    assert wrong_name["error"] == "not_found"


def test_faq_answers_come_from_retrieved_text_and_unknown_is_explicit(
    store: ClinicStore,
) -> None:
    hours = retrieve_clinic_info(store, "What are the clinic opening hours?")
    unknown = retrieve_clinic_info(store, "What is the doctor's personal mobile number?")
    assert hours["found"] is True
    assert all(item.get("answer") for item in hours["retrieved_text"])
    assert unknown["found"] is False
    assert unknown["answer_to_say"] == "I don't know from the clinic information I have."


def test_sample_faq_seeding_is_idempotent(store: ClinicStore, faq_items, settings: Settings) -> None:
    store.initialize(faq_items)
    matches = store.find_faq('"hours"')
    opening_hours = [row for row in matches if "open Monday" in row["answer"]]
    assert len(opening_hours) == 1


def test_escalation_records_only_a_pending_follow_up(store: ClinicStore) -> None:
    result = record_escalation(store, "emergency", "Emergency follow-up requested")
    invalid = record_escalation(store, "medical", "should be rejected")
    assert result["ok"] is True
    assert result["status"] == "pending_staff_follow_up"
    assert "does not connect to staff" in result["message"]
    assert invalid["ok"] is False
    assert invalid["error"] == "invalid_arguments"


def test_sqlite_data_persists_when_store_is_reopened(
    tmp_path: Path, settings: Settings, faq_items
) -> None:
    path = tmp_path / "persistent.sqlite3"
    first_store = ClinicStore(path, settings)
    first_store.initialize(faq_items)
    day = next_workday(settings).isoformat()
    booked = AppointmentTools(first_store, settings).book_appointment(
        day, "09:00", "Persist Person", True
    )
    reopened = ClinicStore(path, settings)
    assert "09:00" not in [slot[-5:] for slot in reopened.available_slots(date.fromisoformat(day))]
    assert AppointmentTools(reopened, settings).cancel_appointment(
        booked["reference_code"], "Persist Person"
    )["ok"] is True
