from dataclasses import replace
from backend.careline.db import ClinicStore
from backend.careline.faq import configured_faq


def test_configured_faq_matches_schedule_and_slot_length(
    tmp_path, settings, faq_items
):
    configured = configured_faq(faq_items, settings)
    store = ClinicStore(tmp_path / "config.sqlite3", settings)
    store.initialize(configured)

    hours = store.find_faq('"hours"')
    booking = store.find_faq('"duration"')
    assert any("Willowbend Family Clinic" in row["answer"] for row in hours)
    assert any("Mon–Fri" in row["answer"] for row in hours)
    assert any("30-minute slots" in row["answer"] for row in booking)

    changed_settings = replace(
        settings,
        clinic_name="Sample Saturday Clinic",
        working_days=(5,),
        clinic_open_time="10:00",
        clinic_close_time="14:00",
        clinic_lunch_start="12:00",
        clinic_lunch_end="12:30",
        appointment_minutes=15,
    )
    store.settings = changed_settings
    store.initialize(configured_faq(faq_items, changed_settings))

    hours = store.find_faq('"hours"')
    booking = store.find_faq('"duration"')
    assert any("Sample Saturday Clinic" in row["answer"] for row in hours)
    assert any("Sat" in row["answer"] and "10 am" in row["answer"] for row in hours)
    assert any("15-minute slots" in row["answer"] for row in booking)

    reduced_faq = [item for item in configured_faq(faq_items, changed_settings)
                   if item["category"] != "fees"]
    store.initialize(reduced_faq)
    assert store.find_faq('"fees"') == []
