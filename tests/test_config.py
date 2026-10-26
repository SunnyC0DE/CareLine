import pytest

from backend.careline.config import Settings


def test_config_rejects_non_hhmm_clinic_time(monkeypatch):
    monkeypatch.setenv("CLINIC_OPEN_TIME", "9am")
    with pytest.raises(ValueError, match="HH:MM"):
        Settings.from_env()


def test_config_rejects_lunch_outside_clinic_opening_hours(monkeypatch):
    monkeypatch.setenv("CLINIC_OPEN_TIME", "09:00")
    monkeypatch.setenv("CLINIC_LUNCH_START", "18:00")
    monkeypatch.setenv("CLINIC_LUNCH_END", "19:00")
    monkeypatch.setenv("CLINIC_CLOSE_TIME", "17:00")
    with pytest.raises(ValueError, match="open < lunch start < lunch end < close"):
        Settings.from_env()
