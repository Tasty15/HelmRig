"""Tester för cron-journal — missed slot detection + journal persistence."""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / ".overlord"))
import cron_journal as cj  # noqa: E402


class TestJournalPersistence:
    def test_load_missing_file(self):
        """Ingen journal-fil → tom dict."""
        orig = cj.JOURNAL_PATH
        cj.JOURNAL_PATH = Path(tempfile.mktemp())
        try:
            assert cj.load_journal() == {}
        finally:
            cj.JOURNAL_PATH = orig

    def test_load_corrupted_json(self):
        """Korrupt JSON → tom dict, ingen krasch."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cron_journal.json"
            path.write_text("{bad json")
            orig = cj.JOURNAL_PATH
            cj.JOURNAL_PATH = path
            try:
                assert cj.load_journal() == {}
            finally:
                cj.JOURNAL_PATH = orig

    def test_save_and_load(self):
        """Save → Load ska returnera samma data."""
        journal = {
            "test-agent": {
                "last_run": "2026-07-22T09:00:00",
                "cron": "0 9 * * 1-5",
                "status": "ok",
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cron_journal.json"
            orig = cj.JOURNAL_PATH
            cj.JOURNAL_PATH = path
            try:
                cj.save_journal(journal)
                loaded = cj.load_journal()
                assert loaded == journal
            finally:
                cj.JOURNAL_PATH = orig

    def test_save_permission_error(self):
        """Ska inte krascha om filen inte går att skriva."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cron_journal.json"
            orig = cj.JOURNAL_PATH
            cj.JOURNAL_PATH = path
            try:
                os.chmod(tmp, 0o444)
                cj.save_journal({"x": {"last_run": "now", "cron": "* * * * *", "status": "ok"}})
            finally:
                cj.JOURNAL_PATH = orig


class TestGetMissedSlots:
    def test_no_missed(self):
        """Agent körde nyss — inga missade slots."""
        now = datetime(2026, 7, 22, 10, 0)
        last_run = "2026-07-22T09:59:00"
        slots = cj.get_missed_slots("0 * * * *", last_run, now)
        assert slots == []

    def test_one_missed(self):
        """En missad slot (09:00) mellan 08:00-10:00."""
        now = datetime(2026, 7, 22, 10, 0)
        last_run = "2026-07-22T08:00:00"
        slots = cj.get_missed_slots("0 * * * *", last_run, now)
        assert len(slots) == 1
        assert slots[0] == datetime(2026, 7, 22, 9, 0)

    def test_two_missed_same_day(self):
        """Två missade slots (09:00, 17:00) samma dag."""
        now = datetime(2026, 7, 15, 20, 0)
        last_run = "2026-07-15T06:00:00"
        slots = cj.get_missed_slots("0 9,17 * * *", last_run, now)
        assert len(slots) == 2
        assert slots[0] == datetime(2026, 7, 15, 9, 0)
        assert slots[1] == datetime(2026, 7, 15, 17, 0)

    def test_invalid_last_run(self):
        """Ogiltigt last_run-datum → tom lista."""
        now = datetime(2026, 7, 22, 10, 0)
        assert cj.get_missed_slots("0 * * * *", "not-a-date", now) == []

    def test_cron_range_and_wildcard(self):
        """Kontorscron 09-17 vardagar. Hela dagen avstängd → 9 slots."""
        now = datetime(2026, 7, 15, 18, 0)  # onsdag
        last_run = "2026-07-15T06:00:00"
        slots = cj.get_missed_slots("0 9-17 * * 1-5", last_run, now)
        assert len(slots) == 9

    def test_weekend_skip(self):
        """Lördag — inga vardagsslots.
        Obs: cron DOW använder Python weekday() (0=Mån, 6=Sön),
        så '0-4' motsvarar Mån-Fre i denna implementation."""
        now = datetime(2026, 7, 18, 20, 0)  # lördag (weekday=5)
        last_run = "2026-07-17T18:00:00"
        slots = cj.get_missed_slots("0 9 * * 0-4", last_run, now)
        assert len(slots) == 0

    def test_broken_cron_expression(self):
        """4-fälts cron → tom lista, ingen krasch."""
        now = datetime(2026, 7, 22, 10, 0)
        assert cj.get_missed_slots("* * * *", "2026-07-22T08:00:00", now) == []

    def test_no_cron_match_at_boundary(self):
        """Slot precis vid now-gränsen ska inte räknas som missad."""
        now = datetime(2026, 7, 22, 10, 0, 0)
        last_run = "2026-07-22T10:00:00"
        slots = cj.get_missed_slots("0 * * * *", last_run, now)
        assert slots == []
