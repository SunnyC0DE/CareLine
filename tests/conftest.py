from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.careline.config import Settings
from backend.careline.db import ClinicStore


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return replace(Settings.from_env(), db_path=tmp_path / "clinic-test.sqlite3")


@pytest.fixture
def faq_items() -> list[dict[str, str]]:
    return json.loads((ROOT / "clinic_faq.json").read_text(encoding="utf-8"))


@pytest.fixture
def store(settings: Settings, faq_items: list[dict[str, str]]) -> ClinicStore:
    clinic_store = ClinicStore(settings.db_path, settings)
    clinic_store.initialize(faq_items)
    return clinic_store
