"""Persistent cron journal + missed slot calculation."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

JOURNAL_PATH = Path(__file__).parent / "cron_journal.json"


def load_journal() -> dict:
    """Load cron journal. Returns {agent_name: {last_run, cron, status}}."""
    if not JOURNAL_PATH.exists():
        return {}
    try:
        return json.loads(JOURNAL_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_journal(journal: dict) -> None:
    """Write cron journal to JSON."""
    try:
        JOURNAL_PATH.write_text(json.dumps(journal, indent=2, ensure_ascii=False))
    except OSError:
        pass  # ponytail: tyst misslyckande — krascha inte daemon


def get_missed_slots(cron_expr: str, last_run: str, now: datetime) -> list[datetime]:
    """Hitta cron-slots mellan last_run och now som missats."""
    try:
        last = datetime.fromisoformat(last_run)
    except (ValueError, TypeError):
        return []

    slots: list[datetime] = []
    current = last + timedelta(minutes=1)
    # ponytail: linjär 1-minuts-sökning. O(10000) för en vecka — gott nog.
    while current < now:
        if _cron_matches(cron_expr, current):
            slots.append(current)
        current += timedelta(minutes=1)
    return slots


# ── Importera cron-matching från overlord (samma mönster) ─────────────

def _cron_field_matches(pattern: str, value: int) -> bool:
    for part in pattern.split(","):
        part = part.strip()
        if part == "*":
            return True
        if "-" in part:
            lo, hi = part.split("-", 1)
            if lo.isdigit() and hi.isdigit() and int(lo) <= value <= int(hi):
                return True
        elif part.isdigit() and int(part) == value:
            return True
    return False


def _cron_matches(expr: str, dt: datetime | None = None) -> bool:
    fields = expr.strip().split()
    if len(fields) != 5:
        return False
    now = dt if dt is not None else datetime.now()
    minute, hour, dom, month, dow = fields
    if not _cron_field_matches(minute, now.minute):
        return False
    if not _cron_field_matches(hour, now.hour):
        return False
    if not _cron_field_matches(dom, now.day):
        return False
    if not _cron_field_matches(month, now.month):
        return False
    if not _cron_field_matches(dow, now.weekday()):
        return False
    return True
