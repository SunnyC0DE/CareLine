from __future__ import annotations

import csv
import json
import sys
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.careline.config import Settings
from backend.careline.db import ClinicStore
from backend.careline.tools.appointments import AppointmentTools
from backend.careline.tools.clinic_info import retrieve_clinic_info
from backend.careline.tools.escalation import record_escalation


SCENARIOS_PATH = ROOT / "eval" / "scenarios.json"
RESULTS_PATH = ROOT / "eval" / "results.csv"


def _next_open_day(settings: Settings, index: int = 1) -> str:
    today = datetime.now(ZoneInfo(settings.clinic_timezone)).date()
    cursor = today
    count = 0
    while count < index:
        cursor += timedelta(days=1)
        if cursor.weekday() in settings.working_days:
            count += 1
    return cursor.isoformat()


def _weekend_day(settings: Settings) -> str:
    cursor = datetime.now(ZoneInfo(settings.clinic_timezone)).date() + timedelta(days=1)
    while cursor.weekday() not in {5, 6}:
        cursor += timedelta(days=1)
    return cursor.isoformat()


def resolve(value: Any, settings: Settings, references: dict[str, str]) -> Any:
    if isinstance(value, dict):
        if set(value) == {"$reference_for"}:
            return references.get(ClinicStore.name_key(str(value["$reference_for"])), "UNKNOWN1")
        return {key: resolve(item, settings, references) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve(item, settings, references) for item in value]
    if not isinstance(value, str):
        return value
    if value == "$NEXT_OPEN_DAY":
        return _next_open_day(settings, 1)
    if value == "$NEXT_OPEN_DAY_2":
        return _next_open_day(settings, 2)
    if value == "$WEEKEND_DAY":
        return _weekend_day(settings)
    if value == "$YESTERDAY":
        return (datetime.now(ZoneInfo(settings.clinic_timezone)).date() - timedelta(days=1)).isoformat()
    if value.startswith("$REF:"):
        name = value.removeprefix("$REF:")
        return references.get(ClinicStore.name_key(name), "UNKNOWN1")
    return value


def tool_dispatch(store: ClinicStore, settings: Settings):
    appointments = AppointmentTools(store, settings)
    # This map invokes fixture-specified tool names; it is not the live agent's action selector.
    return {
        "check_available_slots": lambda **args: appointments.check_available_slots(args["date"]),
        "book_appointment": lambda **args: appointments.book_appointment(
            args["date"], args["time"], args["patient_name"], args["caller_confirmed"]
        ),
        "reschedule_appointment": lambda **args: appointments.reschedule_appointment(**args),
        "cancel_appointment": lambda **args: appointments.cancel_appointment(**args),
        "lookup_clinic_info": lambda **args: retrieve_clinic_info(store, args["question"]),
        "escalate_to_human": lambda **args: record_escalation(store, **args),
    }


def matches(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(actual.get(key) == value for key, value in expected.items())


def evaluate_scenario(scenario: dict[str, Any], settings: Settings, faq_items: list[dict[str, str]]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="careline-eval-") as directory:
        store = ClinicStore(Path(directory) / "eval.sqlite3", settings)
        store.initialize(faq_items)
        dispatch = tool_dispatch(store, settings)
        references: dict[str, str] = {}
        actual_tool_calls: list[str] = []
        checks: list[bool] = []
        error_types: list[str] = []

        for step in scenario["steps"]:
            tool_name = step["tool"]
            if tool_name not in dispatch:
                checks.append(False)
                error_types.append("unregistered_tool")
                continue
            arguments = resolve(step.get("arguments", {}), settings, references)
            try:
                result = dispatch[tool_name](**arguments)
            except Exception as exc:
                checks.append(False)
                error_types.append(type(exc).__name__)
                continue
            actual_tool_calls.append(tool_name)
            checks.append(matches(result, step.get("expect", {})))
            if tool_name == "book_appointment" and result.get("ok") is True:
                patient_name = str(arguments["patient_name"])
                references[ClinicStore.name_key(patient_name)] = result["reference_code"]
            if result.get("error"):
                error_types.append(str(result["error"]))

        expected_calls = scenario.get("expected_tool_calls", [])
        trace_correct = actual_tool_calls == expected_calls
        task_success = all(checks) and len(checks) == len(scenario["steps"])
        return {
            "scenario_id": scenario["id"],
            "category": scenario["category"],
            "task_success": int(task_success),
            "tool_call_correct": int(trace_correct),
            "expected_tool_calls": "|".join(expected_calls),
            "actual_tool_calls": "|".join(actual_tool_calls),
            "step_count": len(scenario["steps"]),
            "passed_steps": sum(checks),
            "error_types": "|".join(error_types),
            "trace_source": "hand-authored-gold-trace; no LLM inference",
        }


def run() -> list[dict[str, Any]]:
    settings = Settings.from_env()
    faq_items = json.loads((ROOT / "clinic_faq.json").read_text(encoding="utf-8"))
    dataset = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    scenarios = dataset["scenarios"]
    rows = [evaluate_scenario(scenario, settings, faq_items) for scenario in scenarios]
    columns = list(rows[0])
    with RESULTS_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    passed_tasks = sum(int(row["task_success"]) for row in rows)
    correct_traces = sum(int(row["tool_call_correct"]) for row in rows)
    categories = Counter(row["category"] for row in rows)
    print(f"Scenarios: {len(rows)}")
    print(f"Tool/database task outcomes: {passed_tasks}/{len(rows)} ({passed_tasks / len(rows) * 100:.1f}%)")
    print(f"Gold tool trace comparison: {correct_traces}/{len(rows)} ({correct_traces / len(rows) * 100:.1f}%)")
    print("Category counts:", ", ".join(f"{key}={value}" for key, value in sorted(categories.items())))
    print(f"Results saved to {RESULTS_PATH.relative_to(ROOT)}")
    print("Note: tool-call correctness compares the fixture's declared trace, not a live LLM decision.")
    return rows


if __name__ == "__main__":
    run()
