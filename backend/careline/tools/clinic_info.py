from __future__ import annotations

import asyncio
from typing import Any

from pipecat.services.llm_service import FunctionCallParams

from backend.careline.db import ClinicStore
from backend.careline.schemas import FAQArgs


_STOP_WORDS = {"a", "an", "the", "is", "are", "do", "does", "can", "could", "what", "when", "where", "how", "my", "your", "you", "i", "me", "of", "to", "for", "in", "on", "and", "or", "please", "tell", "about", "clinic"}


def _fts_query(text: str) -> str:
    terms = []
    for raw in text.casefold().split():
        term = raw.strip(".,!?;:'\"()[]{}<>/\\")
        if len(term) > 1 and term not in _STOP_WORDS and term.isalnum():
            terms.append(f'"{term}"')
    return " OR ".join(dict.fromkeys(terms))


def retrieve_clinic_info(store: ClinicStore, question: str) -> dict[str, Any]:
    try:
        args = FAQArgs(question=question)
    except Exception as exc:
        return {"found": False, "answer_to_say": "I don't know from the clinic information I have.", "error": str(exc)}
    terms = _fts_query(args.question)
    try:
        matches = store.find_faq(terms)
    except Exception:
        matches = []
    if not matches:
        return {
            "found": False,
            "answer_to_say": "I don't know from the clinic information I have.",
            "retrieved_text": [],
        }
    return {
        "found": True,
        "retrieved_text": [
            {"question": row["question"], "answer": row["answer"]}
            for row in matches
        ],
        "instruction": "Answer only with facts in retrieved_text. Do not add other clinic claims.",
    }


def make_lookup_clinic_info(store: ClinicStore):
    async def lookup_clinic_info(params: FunctionCallParams, question: str) -> None:
        """Retrieve a relevant passage from the clinic FAQ; never answer from memory.

        Args:
            question: The caller's question about clinic hours, services, fees, or policies.
        """
        result = await asyncio.to_thread(retrieve_clinic_info, store, question)
        await params.result_callback(result)

    return lookup_clinic_info
