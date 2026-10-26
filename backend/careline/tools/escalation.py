from __future__ import annotations

import asyncio
import uuid
from typing import Any

from pydantic import ValidationError
from pipecat.services.llm_service import FunctionCallParams

from backend.careline.db import ClinicStore
from backend.careline.schemas import EscalationArgs


def record_escalation(store: ClinicStore, category: str, brief_reason: str) -> dict[str, Any]:
    try:
        args = EscalationArgs(category=category, brief_reason=brief_reason)
    except ValidationError as exc:
        return {"ok": False, "error": "invalid_arguments", "message": str(exc)}
    escalation_id = uuid.uuid4().hex[:12].upper()
    try:
        store.create_escalation(escalation_id, args.category)
    except Exception:
        return {"ok": False, "error": "storage_error", "message": "The follow-up request could not be recorded."}
    return {
        "ok": True,
        "status": "pending_staff_follow_up",
        "request_id": escalation_id,
        "message": "This demo records a follow-up request but does not connect to staff. Do not promise a live transfer; for an emergency, contact local emergency services now.",
    }


def make_escalate_to_human(store: ClinicStore):
    async def escalate_to_human(
        params: FunctionCallParams, category: str, brief_reason: str
    ) -> None:
        """Record a request for clinic staff follow-up for emergencies or out-of-scope needs.

        Args:
            category: One of emergency, out_of_scope, staff_request, or other.
            brief_reason: A short category-level reason; do not include medical details or patient identifiers.
        """
        result = await asyncio.to_thread(record_escalation, store, category, brief_reason)
        await params.result_callback(result)

    return escalate_to_human
