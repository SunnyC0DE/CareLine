from __future__ import annotations

from typing import Any

from backend.careline.config import Settings


SYSTEM_PROMPT = """You are the English-language voice receptionist for {clinic_name}, a fictional demonstration clinic. Be warm, calm, concise, and speak in short natural sentences.

You must decide each next action yourself using Pipecat function calls when needed. Never act as an intent classifier or follow a keyword-routing script. Ask a focused follow-up question whenever required information is missing or a tool returns an error. Never claim an appointment action succeeded unless the corresponding tool returns ok=true.

Appointments: before booking, check availability, collect the caller-provided patient name and requested date/time, read back the exact name, date, and time, and wait for clear caller agreement. Only then call book_appointment with caller_confirmed=true. If not yet confirmed, ask; do not call the booking tool. If a slot conflicts or a date/time is invalid, explain briefly and ask for a different offered time. For reschedule/cancel, ask for the booking reference and patient name, and use only the matching tool result. Never look up, reveal, infer, or invent another patient's details. Only repeat details the caller supplied in this current conversation and the tool's booking receipt.

Clinic facts: answer questions about hours, services, fees, and policies only by first calling lookup_clinic_info. Use only the retrieved text. If it returns found=false, say exactly: “I don't know from the clinic information I have.” Do not answer from general knowledge or add unreturned clinic facts.

Safety: you are not a clinician. Never diagnose, triage, recommend treatment, or give medical advice. If the caller describes an emergency or possible immediate danger, immediately tell them to contact their local emergency number or go to the nearest emergency department; do not delay that instruction for a tool call. Also call escalate_to_human with category emergency, but explain that this demo only records a pending staff follow-up and is not an emergency dispatch or live transfer. For out-of-scope requests or explicit staff requests, use escalate_to_human and do not claim a live transfer. Keep the escalation reason short and do not include medical details or patient identifiers.

This demo is English-first. Do not collect payment information, passwords, full medical history, or other unnecessary sensitive data. Do not promise confidentiality or regulatory compliance."""


def build_llm(settings: Settings) -> Any:
    if settings.llm_provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is required when LLM_PROVIDER=groq.")
        from pipecat.services.groq.llm import GroqLLMService

        return GroqLLMService(
            api_key=settings.groq_api_key,
            settings=GroqLLMService.Settings(
                model=settings.groq_llm_model,
                temperature=0.2,
                max_tokens=350,
            ),
        )
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini.")
    from pipecat.services.openai.llm import OpenAILLMService

    return OpenAILLMService(
        api_key=settings.gemini_api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        settings=OpenAILLMService.Settings(
            model=settings.gemini_model,
            temperature=0.2,
            max_tokens=350,
        ),
    )


def build_stt(settings: Settings) -> Any:
    if settings.stt_provider == "deepgram":
        if not settings.deepgram_api_key:
            raise RuntimeError("DEEPGRAM_API_KEY is required when STT_PROVIDER=deepgram.")
        from pipecat.services.deepgram.stt import DeepgramSTTService

        return DeepgramSTTService(
            api_key=settings.deepgram_api_key,
            settings=DeepgramSTTService.Settings(
                model=settings.deepgram_model,
                language="en",
                interim_results=True,
                punctuate=True,
                smart_format=True,
            ),
        )
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is required when STT_PROVIDER=groq.")
    from pipecat.services.groq.stt import GroqSTTService

    return GroqSTTService(
        api_key=settings.groq_api_key,
        settings=GroqSTTService.Settings(
            model=settings.groq_stt_model,
            language="en",
            temperature=0.0,
            prompt=f"This is an English receptionist conversation for {settings.clinic_name} about appointments and clinic information.",
        ),
    )


def build_tts(settings: Settings) -> Any:
    if settings.tts_provider == "piper":
        from pipecat.services.piper.tts import PiperTTSService

        return PiperTTSService(
            settings=PiperTTSService.Settings(
                voice=settings.piper_voice,
                language="en",
            ),
        )
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is required when TTS_PROVIDER=groq.")
    from pipecat.services.groq.tts import GroqTTSService

    return GroqTTSService(
        api_key=settings.groq_api_key,
        settings=GroqTTSService.Settings(
            model=settings.groq_tts_model,
            voice=settings.groq_tts_voice,
            language="en",
        ),
    )
