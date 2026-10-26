from __future__ import annotations

from datetime import time
from typing import Any

from backend.careline.config import Settings

DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
DAY_ABBREVIATIONS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def display_time(raw_time: str) -> str:
    value = time.fromisoformat(raw_time).strftime("%I:%M %p").lstrip("0").lower()
    return value.replace(":00", "")


def display_working_days(days: tuple[int, ...]) -> str:
    abbreviations = [DAY_ABBREVIATIONS[day] for day in days]
    if len(days) > 1 and tuple(days) == tuple(range(days[0], days[-1] + 1)):
        return f"{abbreviations[0]}–{abbreviations[-1]}"
    return ", ".join(abbreviations)


def configured_faq(items: list[dict[str, Any]], settings: Settings) -> list[dict[str, Any]]:
    """Return sample FAQ rows with scheduling facts aligned to the active clinic settings."""
    result = [dict(item) for item in items]
    working_days = [DAY_NAMES[day] for day in settings.working_days]
    day_text = display_working_days(settings.working_days)
    if len(settings.working_days) == 7:
        closing_text = "The clinic is open every day during the posted hours."
    else:
        closing_text = "The clinic is closed on other days."

    for item in result:
        if item.get("category") == "hours":
            item["answer"] = (
                f"{settings.clinic_name} is open {day_text} from "
                f"{display_time(settings.clinic_open_time)} to "
                f"{display_time(settings.clinic_lunch_start)} and "
                f"{display_time(settings.clinic_lunch_end)} to "
                f"{display_time(settings.clinic_close_time)}. "
                f"{closing_text} The clinic is closed during the lunch break."
            )
            item["keywords"] = "hours opening time schedule weekdays weekend lunch"
        elif item.get("category") == "booking":
            item["answer"] = (
                f"Routine appointments are scheduled in {settings.appointment_minutes}-minute slots. "
                "The receptionist checks current availability before offering a time."
            )
            item["keywords"] = "appointment length duration slot availability"
    return result
