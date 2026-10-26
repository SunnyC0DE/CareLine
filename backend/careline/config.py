from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    stt_provider: str
    tts_provider: str
    groq_api_key: str
    deepgram_api_key: str
    gemini_api_key: str
    groq_llm_model: str
    gemini_model: str
    deepgram_model: str
    groq_stt_model: str
    groq_tts_model: str
    groq_tts_voice: str
    piper_voice: str
    clinic_name: str
    clinic_timezone: str
    clinic_open_time: str
    clinic_close_time: str
    clinic_lunch_start: str
    clinic_lunch_end: str
    appointment_minutes: int
    working_days: tuple[int, ...]
    db_path: Path
    port: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        llm_provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
        stt_provider = os.getenv("STT_PROVIDER", "deepgram").strip().lower()
        tts_provider = os.getenv("TTS_PROVIDER", "piper").strip().lower()
        if llm_provider not in {"groq", "gemini"}:
            raise ValueError("LLM_PROVIDER must be 'groq' or 'gemini'.")
        if stt_provider not in {"deepgram", "groq"}:
            raise ValueError("STT_PROVIDER must be 'deepgram' or 'groq'.")
        if tts_provider not in {"piper", "groq"}:
            raise ValueError("TTS_PROVIDER must be 'piper' or 'groq'.")

        timezone_name = os.getenv("CLINIC_TIMEZONE", "Asia/Kolkata").strip()
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("CLINIC_TIMEZONE must be a valid IANA timezone name.") from exc

        raw_days = os.getenv("WORKING_DAYS", "0,1,2,3,4")
        try:
            working_days = tuple(sorted({int(day.strip()) for day in raw_days.split(",")}))
        except ValueError as exc:
            raise ValueError("WORKING_DAYS must be comma-separated integers from 0 through 6.") from exc
        if not working_days or any(day < 0 or day > 6 for day in working_days):
            raise ValueError("WORKING_DAYS must include valid weekdays from 0 through 6.")

        schedule_values = {
            "CLINIC_OPEN_TIME": os.getenv("CLINIC_OPEN_TIME", "09:00").strip(),
            "CLINIC_LUNCH_START": os.getenv("CLINIC_LUNCH_START", "12:00").strip(),
            "CLINIC_LUNCH_END": os.getenv("CLINIC_LUNCH_END", "13:00").strip(),
            "CLINIC_CLOSE_TIME": os.getenv("CLINIC_CLOSE_TIME", "17:00").strip(),
        }
        try:
            parsed_times = {
                name: time.fromisoformat(value)
                for name, value in schedule_values.items()
            }
            if any(value.strftime("%H:%M") != schedule_values[name] for name, value in parsed_times.items()):
                raise ValueError
        except ValueError as exc:
            raise ValueError("Clinic opening, lunch, and closing times must use HH:MM format.") from exc
        if not (
            parsed_times["CLINIC_OPEN_TIME"]
            < parsed_times["CLINIC_LUNCH_START"]
            < parsed_times["CLINIC_LUNCH_END"]
            < parsed_times["CLINIC_CLOSE_TIME"]
        ):
            raise ValueError(
                "Clinic times must be ordered: open < lunch start < lunch end < close."
            )

        minutes = int(os.getenv("APPOINTMENT_MINUTES", "30"))
        if minutes < 5 or minutes > 120:
            raise ValueError("APPOINTMENT_MINUTES must be between 5 and 120.")
        port = int(os.getenv("PORT", "3000"))
        if not 1024 <= port <= 65535:
            raise ValueError("PORT must be between 1024 and 65535.")

        return cls(
            llm_provider=llm_provider,
            stt_provider=stt_provider,
            tts_provider=tts_provider,
            groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
            deepgram_api_key=os.getenv("DEEPGRAM_API_KEY", "").strip(),
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            groq_llm_model=os.getenv("GROQ_LLM_MODEL", "openai/gpt-oss-20b").strip(),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip(),
            deepgram_model=os.getenv("DEEPGRAM_MODEL", "nova-3-general").strip(),
            groq_stt_model=os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo").strip(),
            groq_tts_model=os.getenv("GROQ_TTS_MODEL", "canopylabs/orpheus-v1-english").strip(),
            groq_tts_voice=os.getenv("GROQ_TTS_VOICE", "autumn").strip(),
            piper_voice=os.getenv("PIPER_VOICE", "en_US-lessac-medium").strip(),
            clinic_name=os.getenv("CLINIC_NAME", "Willowbend Family Clinic").strip(),
            clinic_timezone=timezone_name,
            clinic_open_time=schedule_values["CLINIC_OPEN_TIME"],
            clinic_close_time=schedule_values["CLINIC_CLOSE_TIME"],
            clinic_lunch_start=schedule_values["CLINIC_LUNCH_START"],
            clinic_lunch_end=schedule_values["CLINIC_LUNCH_END"],
            appointment_minutes=minutes,
            working_days=working_days,
            db_path=Path(os.getenv("CARELINE_DB_PATH", "data/careline.sqlite3")),
            port=port,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )


def get_settings() -> Settings:
    return Settings.from_env()
