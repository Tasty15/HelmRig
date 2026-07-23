#!/usr/bin/env python3
"""Overlord daemon — cron scheduler + health checks + log rotation."""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import threading
from concurrent.futures import ThreadPoolExecutor

import yaml

OVERLORD_DIR = Path(__file__).parent
AGENTS_DIR = OVERLORD_DIR.parent
LOGS_DIR = OVERLORD_DIR / "logs"
LOG_FILE = OVERLORD_DIR / "watchdog.log"
PID_FILE = OVERLORD_DIR / "overlord.pid"
VENV_PYTHON = AGENTS_DIR.parent / ".venv" / "bin" / "python3"

sys.path.insert(0, str(AGENTS_DIR))
from harness import _list_agents, _read_config as _read_agent_config  # noqa: E402
from cron_journal import load_journal, save_journal, get_missed_slots  # noqa: E402

RUNNING = True
AGENT_LOCKS: dict[str, float] = {}  # agent_name → timestamp när den startades

# Thread-safe per-agent lås (ersätter PID-filer för parallell cron)
_agent_run_locks: dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()


def _get_agent_lock(name: str) -> threading.Lock:
    with _locks_lock:
        if name not in _agent_run_locks:
            _agent_run_locks[name] = threading.Lock()
        return _agent_run_locks[name]


def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _rotate_logs(retention_days: int = 30):
    """Ta bort JSONL-loggar äldre än retention_days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_str = cutoff.isoformat()
    for f in LOGS_DIR.glob("*.jsonl"):
        try:
            lines = [l for l in f.read_text().splitlines() if l.strip()]
            if not lines:
                continue
            parsed = []
            for l in lines:
                try:
                    e = json.loads(l)
                    if e.get("ts", "") >= cutoff_str:
                        parsed.append(l)
                except json.JSONDecodeError:
                    parsed.append(l)
            # Behåll minst 10 rader — lägg till senaste från originalfilen om för få
            if len(parsed) < 10:
                seen = set(parsed)
                for l in reversed(lines):
                    if len(parsed) >= 10:
                        break
                    if l not in seen:
                        parsed.insert(0, l)
                        seen.add(l)
            f.write_text("\n".join(parsed) + "\n")
        except Exception:
            pass


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


def _run_agent(agent_dir: Path, cron_expr: str | None = None) -> str:
    """Kör en agents main.py — skyddad av PID-lock mot dubbla körningar.

    Returns status string: "ok", "fail", "timeout", "skip".
    """
    agent_name = agent_dir.name
    main_py = agent_dir / "main.py"
    if not main_py.exists():
        _log(f"CRON SKIP {agent_name} — ingen main.py")
        _update_journal(agent_name, cron_expr, "skip")
        return "skip"

    # Concurrency-skydd: in-memory lock per agent (thread-safe, fungerar med parallell cron)
    lock = _get_agent_lock(agent_name)
    if not lock.acquire(blocking=False):
        _log(f"CRON SKIP {agent_name} — körs redan")
        return "skip"

    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else "python3"
    AGENT_LOCKS[agent_name] = time.time()
    _log(f"CRON RUN {agent_name}")

    start = time.time()
    try:
        result = subprocess.run(
            [python, str(main_py)],
            capture_output=True, text=True, timeout=120,
        )
        duration = time.time() - start
        if result.returncode == 0:
            _log(f"CRON OK {agent_name} ({duration:.1f}s)")
            _update_journal(agent_name, cron_expr, "ok")
            return "ok"
        else:
            _log(f"CRON FAIL {agent_name} ({duration:.1f}s): {result.stderr[:200]}")
            _update_journal(agent_name, cron_expr, "fail")
            return "fail"
    except subprocess.TimeoutExpired:
        _log(f"CRON FAIL {agent_name} — timeout (120s)")
        _update_journal(agent_name, cron_expr, "timeout")
        return "timeout"
    finally:
        lock.release()
        AGENT_LOCKS.pop(agent_name, None)


def _load_config() -> dict:
    cfg_path = OVERLORD_DIR / "config.yaml"
    if not cfg_path.exists():
        return {}
    try:
        return yaml.safe_load(cfg_path.read_text()) or {}
    except Exception:
        return {}


def health_check(agent_dir: Path, cfg: dict) -> None:
    agent_name = agent_dir.name
    main_py = agent_dir / "main.py"
    if main_py.exists():
        try:
            compile(main_py.read_text(), str(main_py), "exec")
        except SyntaxError as e:
            _log(f"ERROR {agent_name} — syntaxfel i main.py: {e}")


def _stale_lock_cleanup():
    """Rensa PID-lockar äldre än 2 timmar (process dog utan att rensa)."""
    lock_dir = OVERLORD_DIR / "locks"
    if not lock_dir.exists():
        return
    cutoff = time.time() - 7200
    for f in lock_dir.glob("*.pid"):
        try:
            if f.stat().st_mtime < cutoff:
                pid = int(f.read_text().strip())
                try:
                    os.kill(pid, 0)
                except (ProcessLookupError, OSError):
                    f.unlink(missing_ok=True)
        except Exception:
            f.unlink(missing_ok=True)


def _update_journal(agent_name: str, cron: str | None, status: str):
    """Uppdatera cron-journalen efter en agentkörning."""
    if not cron:
        return
    journal = load_journal()
    journal[agent_name] = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "cron": cron,
        "status": status,
    }
    save_journal(journal)


def _catch_up(config: dict):
    """Kör missade cron-jobb sedan senaste Overlord-körning."""
    journal = load_journal()
    catch_up_defaults = {"mode": "queue", "max_missed": 5, "ttl_minutes": 120}
    now = datetime.now()

    for agent_dir in _list_agents():
        cfg = _read_agent_config(agent_dir) or {}
        agent_name = agent_dir.name
        cron = cfg.get("cron")
        if not cron:
            continue

        entry = journal.get(agent_name, {})
        last_run = entry.get("last_run") if isinstance(entry, dict) else None
        if not last_run:
            continue  # ny agent, ingen historik

        # Sök 7 dagar bakåt — om last_run är äldre än så, capa för prestanda
        lookback_limit = now - timedelta(days=7)
        try:
            last_dt = datetime.fromisoformat(last_run)
        except (ValueError, TypeError):
            continue
        effective_last = max(last_dt, lookback_limit)

        slots = get_missed_slots(cron, effective_last.isoformat(), now)
        if not slots:
            continue

        catch_up = cfg.get("catch_up", {})
        if isinstance(catch_up, dict):
            pass
        else:
            catch_up = {}
        mode = catch_up.get("mode", catch_up_defaults["mode"])
        max_missed = catch_up.get("max_missed", catch_up_defaults["max_missed"])
        ttl = catch_up.get("ttl_minutes", catch_up_defaults["ttl_minutes"])

        # Filtrera: TTL
        filtered = [s for s in slots if (now - s).total_seconds() / 60 <= ttl]
        expired = len(slots) - len(filtered)
        for s in slots:
            if (now - s).total_seconds() / 60 > ttl:
                _log(f"CATCH-UP SKIP {agent_name} — missad slot {s.isoformat()} (TTL {ttl}m utgången)")

        # Capa: max_missed
        if len(filtered) > max_missed:
            _log(f"CATCH-UP CAP {agent_name} — {len(filtered)} missade slots, kör de {max_missed} senaste")
            filtered = filtered[-max_missed:]

        _log(f"CATCH-UP {agent_name} — {len(slots)} missade slots (TTL-bort: {expired}, kör: {len(filtered)})")

        if mode == "skip":
            continue

        for slot in filtered:
            _log(f"CATCH-UP RUN {agent_name} — slot {slot.isoformat()}")
            _run_agent(agent_dir, cron)

    # Spara journal efter catch-up
    save_journal(load_journal())


def main():
    global RUNNING

    def handle_signal(sig, frame):
        global RUNNING
        _log("Overlord stoppar...")
        RUNNING = False

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    _log("Overlord startad")

    config = _load_config()
    interval = config.get("watchdog", {}).get("interval_s", 60)
    retention = config.get("log_retention_days", 30)
    max_concurrent = config.get("watchdog", {}).get("max_concurrent_cron", 1)
    cron_tracker: dict[str, str] = {}
    rotate_every = max(interval * 60, 3600)  # Rotera loggar max 1 gång/timme
    last_rotate = 0.0

    # Catch-up: kör missade cron-jobb från förra sessionen
    _catch_up(config)

    while RUNNING:
        now = datetime.now()
        now_ts = time.time()
        cron_minute = now.strftime("%Y%m%d%H%M")

        # Log rotation (en gång i timmen)
        if now_ts - last_rotate >= rotate_every:
            _rotate_logs(retention)
            _stale_lock_cleanup()
            last_rotate = now_ts

        # Schemalägg cron-jobb
        to_run = []
        for agent_dir in _list_agents():
            cfg = _read_agent_config(agent_dir) or {}
            agent_name = agent_dir.name
            cron = cfg.get("cron")
            if cron and cron_tracker.get(agent_name) != cron_minute and _cron_matches(cron):
                cron_tracker[agent_name] = cron_minute
                to_run.append(agent_dir)

        # Health checks
        for agent_dir in _list_agents():
            cfg = _read_agent_config(agent_dir) or {}
            health_check(agent_dir, cfg)

        # Kör cron-jobb (parallellt om max_concurrent > 1)
        if to_run:
            if max_concurrent > 1:
                with ThreadPoolExecutor(max_workers=max_concurrent) as ex:
                    cfg_map = {
                        d: (_read_agent_config(d) or {}).get("cron")
                        for d in to_run
                    }
                    # ponytail: list() driver executor.map så alla tasks startar
                    list(ex.map(lambda d: _run_agent(d, cfg_map[d]), to_run))
            else:
                for agent_dir in to_run:
                    cfg = _read_agent_config(agent_dir) or {}
                    _run_agent(agent_dir, cfg.get("cron"))

        # Vänta
        for _ in range(interval):
            if not RUNNING:
                break
            time.sleep(1)

    _log("Overlord stoppad")


if __name__ == "__main__":
    main()
