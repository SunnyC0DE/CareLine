from __future__ import annotations

from pipecat.processors.aggregators.llm_context import LLMContext

from backend.careline.config import Settings
from backend.careline.db import ClinicStore
from backend.careline.voice.pipeline import build_tools


def test_six_expected_tools_are_llm_function_callables(store: ClinicStore, settings: Settings) -> None:
    context = LLMContext(tools=build_tools(store, settings))
    names = {schema.name for schema in context.tools.standard_tools}
    assert names == {
        "check_available_slots",
        "book_appointment",
        "reschedule_appointment",
        "cancel_appointment",
        "lookup_clinic_info",
        "escalate_to_human",
    }
