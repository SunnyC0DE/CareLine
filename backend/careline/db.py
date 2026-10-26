from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

from backend.careline.config import Settings


class ClinicStore:
    """SQLite persistence for synthetic/demo clinic data and appointment actions."""

    def __init__(self, db_path: str | Path, settings: Settings):
        self.db_path = str(db_path)
        self.settings = settings

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        if self.db_path != ":memory:":
            Path(self.db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=8, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 8000")
        try:
            yield conn
        finally:
            conn.close()

    def initialize(self, faq_items: list[dict[str, str]] | None = None) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference_hash TEXT NOT NULL UNIQUE,
                    patient_name TEXT NOT NULL,
                    name_key TEXT NOT NULL,
                    start_local TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('booked', 'cancelled')),
                    created_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS unique_active_appointment_slot
                    ON appointments(start_local) WHERE status = 'booked';

                CREATE TABLE IF NOT EXISTS clinic_faq (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    keywords TEXT NOT NULL DEFAULT ''
                );
                CREATE UNIQUE INDEX IF NOT EXISTS unique_clinic_faq_entry
                    ON clinic_faq(category, question);
                CREATE VIRTUAL TABLE IF NOT EXISTS clinic_faq_fts USING fts5(
                    question, answer, keywords
                );

                CREATE TABLE IF NOT EXISTS escalations (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL
                );
                """
            )
            if faq_items is not None:
                current_faq_keys = {
                    (item["category"], item["question"]) for item in faq_items
                }
                existing_faq_keys = conn.execute(
                    "SELECT category, question FROM clinic_faq"
                ).fetchall()
                stale_faq_keys = [
                    (row["category"], row["question"])
                    for row in existing_faq_keys
                    if (row["category"], row["question"]) not in current_faq_keys
                ]
                conn.executemany(
                    "DELETE FROM clinic_faq WHERE category = ? AND question = ?",
                    stale_faq_keys,
                )
                for item in faq_items:
                    conn.execute(
                        "INSERT INTO clinic_faq(category, question, answer, keywords) VALUES (?, ?, ?, ?) "
                        "ON CONFLICT(category, question) DO UPDATE SET "
                        "answer = excluded.answer, keywords = excluded.keywords",
                        (item["category"], item["question"], item["answer"], item.get("keywords", "")),
                    )
            conn.execute("DELETE FROM clinic_faq_fts")
            conn.execute(
                "INSERT INTO clinic_faq_fts(rowid, question, answer, keywords) "
                "SELECT id, question, answer, keywords FROM clinic_faq"
            )

    @staticmethod
    def name_key(name: str) -> str:
        return " ".join(name.casefold().split())

    @staticmethod
    def hash_reference(reference: str) -> str:
        return hashlib.sha256(reference.strip().upper().encode("utf-8")).hexdigest()

    def scheduled_slots(self, day: date) -> list[str]:
        if day.weekday() not in self.settings.working_days:
            return []
        start = time.fromisoformat(self.settings.clinic_open_time)
        close = time.fromisoformat(self.settings.clinic_close_time)
        lunch_start = time.fromisoformat(self.settings.clinic_lunch_start)
        lunch_end = time.fromisoformat(self.settings.clinic_lunch_end)
        cursor = datetime.combine(day, start)
        closing = datetime.combine(day, close)
        slot = timedelta(minutes=self.settings.appointment_minutes)
        lunch_from = datetime.combine(day, lunch_start)
        lunch_to = datetime.combine(day, lunch_end)
        slots: list[str] = []
        while cursor + slot <= closing:
            candidate_end = cursor + slot
            overlaps_lunch = cursor < lunch_to and candidate_end > lunch_from
            if not overlaps_lunch:
                slots.append(cursor.strftime("%Y-%m-%dT%H:%M"))
            cursor += slot
        return slots

    def available_slots(self, day: date) -> list[str]:
        possible = self.scheduled_slots(day)
        if not possible:
            return []
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT start_local FROM appointments WHERE status = 'booked' AND start_local LIKE ?",
                (f"{day.isoformat()}T%",),
            ).fetchall()
        booked = {str(row["start_local"]) for row in rows}
        return [slot for slot in possible if slot not in booked]

    def book(self, patient_name: str, name_key: str, start_local: str, reference: str) -> bool:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                if start_local not in self.scheduled_slots(date.fromisoformat(start_local[:10])):
                    conn.execute("ROLLBACK")
                    return False
                conn.execute(
                    "INSERT INTO appointments(reference_hash, patient_name, name_key, start_local, status, created_at) "
                    "VALUES (?, ?, ?, ?, 'booked', ?)",
                    (
                        self.hash_reference(reference),
                        patient_name,
                        name_key,
                        start_local,
                        datetime.now(ZoneInfo(self.settings.clinic_timezone)).isoformat(timespec="seconds"),
                    ),
                )
                conn.execute("COMMIT")
                return True
            except sqlite3.IntegrityError:
                conn.execute("ROLLBACK")
                return False
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def reschedule(
        self, reference: str, name_key: str, new_start_local: str
    ) -> tuple[bool, str | None]:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    "SELECT id FROM appointments WHERE reference_hash = ? AND name_key = ? AND status = 'booked'",
                    (self.hash_reference(reference), name_key),
                ).fetchone()
                if row is None:
                    conn.execute("ROLLBACK")
                    return False, "not_found"
                slot_day = date.fromisoformat(new_start_local[:10])
                if new_start_local not in self.scheduled_slots(slot_day):
                    conn.execute("ROLLBACK")
                    return False, "invalid_slot"
                conn.execute(
                    "UPDATE appointments SET start_local = ? WHERE id = ?",
                    (new_start_local, row["id"]),
                )
                conn.execute("COMMIT")
                return True, None
            except sqlite3.IntegrityError:
                conn.execute("ROLLBACK")
                return False, "slot_taken"
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def cancel(self, reference: str, name_key: str) -> bool:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = conn.execute(
                    "UPDATE appointments SET status = 'cancelled' "
                    "WHERE reference_hash = ? AND name_key = ? AND status = 'booked'",
                    (self.hash_reference(reference), name_key),
                )
                conn.execute("COMMIT")
                return cursor.rowcount == 1
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def find_faq(self, terms: str, limit: int = 3) -> list[dict[str, Any]]:
        if not terms.strip():
            return []
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT question, answer, keywords, bm25(clinic_faq_fts) AS rank "
                "FROM clinic_faq_fts WHERE clinic_faq_fts MATCH ? ORDER BY rank LIMIT ?",
                (terms, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_escalation(self, escalation_id: str, category: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO escalations(id, category, status, created_at) VALUES (?, ?, 'pending', ?)",
                (
                    escalation_id,
                    category,
                    datetime.now(ZoneInfo(self.settings.clinic_timezone)).isoformat(timespec="seconds"),
                ),
            )
