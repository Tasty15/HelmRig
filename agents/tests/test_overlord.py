"""Tester för overlord daemon — cron-matching, log rotation, concurrency."""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / ".overlord"))


class TestCronMatching:
    """_cron_field_matches och _cron_matches."""

    def test_field_wildcard(self):
        from overlord import _cron_field_matches
        assert _cron_field_matches("*", 5) is True
        assert _cron_field_matches("*", 0) is True
        assert _cron_field_matches("*", 59) is True

    def test_field_exact(self):
        from overlord import _cron_field_matches
        assert _cron_field_matches("30", 30) is True
        assert _cron_field_matches("30", 31) is False

    def test_field_range(self):
        from overlord import _cron_field_matches
        assert _cron_field_matches("1-5", 3) is True
        assert _cron_field_matches("1-5", 0) is False
        assert _cron_field_matches("1-5", 6) is False

    def test_field_comma(self):
        from overlord import _cron_field_matches
        assert _cron_field_matches("0,15,30,45", 30) is True
        assert _cron_field_matches("0,15,30,45", 7) is False

    def test_cron_full_expression(self):
        from overlord import _cron_matches
        from datetime import datetime
        now = datetime.now()
        expr = f"{now.minute} {now.hour} {now.day} {now.month} *"
        assert _cron_matches(expr) is True

    def test_cron_no_match(self):
        from overlord import _cron_matches
        assert _cron_matches("99 99 99 99 99") is False

    def test_cron_invalid_fields(self):
        from overlord import _cron_matches
        assert _cron_matches("") is False
        assert _cron_matches("* * * *") is False  # 4 fields
        assert _cron_matches("* * * * * *") is False  # 6 fields


class TestLogRotation:
    def test_rotate_removes_old_entries(self):
        from overlord import _rotate_logs
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            f = log_dir / "test.jsonl"
            old_ts = "2020-01-01T00:00:00"
            new_ts = "2026-07-22T00:00:00"
            # 5 gamla + 12 nya = 17 totalt (mer än 10 nya, padding behövs inte)
            lines = [json.dumps({"ts": old_ts, "agent": "test"}) for _ in range(5)]
            lines += [json.dumps({"ts": new_ts, "agent": "test"}) for _ in range(12)]
            f.write_text("\n".join(lines) + "\n")
            with patch("overlord.LOGS_DIR", log_dir):
                _rotate_logs(retention_days=7)
            remaining = f.read_text().splitlines()
            assert 10 <= len(remaining) <= 12  # 12 nya, padding max 10
            assert all(new_ts in l for l in remaining)  # inga gamla kvar

    def test_rotate_keeps_min_10(self):
        from overlord import _rotate_logs
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            f = log_dir / "test.jsonl"
            old_ts = "2020-01-01T00:00:00"
            lines = [json.dumps({"ts": old_ts, "agent": f"test{x}"}) for x in range(15)]
            f.write_text("\n".join(lines) + "\n")
            with patch("overlord.LOGS_DIR", log_dir):
                _rotate_logs(retention_days=7)
            remaining = f.read_text().splitlines()
            assert len(remaining) == 10  # minst 10 behålls

    def test_rotate_invalid_json(self):
        from overlord import _rotate_logs
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            f = log_dir / "test.jsonl"
            f.write_text("not-json\n{\"ts\": \"2026-07-22T00:00:00\"}\n")
            with patch("overlord.LOGS_DIR", log_dir):
                _rotate_logs(retention_days=7)
            assert f.exists()


class TestConcurrencyLocks:
    def test_stale_lock_cleanup(self):
        from overlord import _stale_lock_cleanup
        with tempfile.TemporaryDirectory() as tmp:
            lock_dir = Path(tmp) / "locks"
            lock_dir.mkdir(parents=True)
            # Skapa en gammal lock-fil (ingen levande process)
            old_lock = lock_dir / "old.pid"
            old_lock.write_text("999999")
            # sätt mtime långt bak
            old_mtime = time.time() - 10000
            os.utime(old_lock, (old_mtime, old_mtime))
            with patch("overlord.OVERLORD_DIR", Path(tmp)):
                _stale_lock_cleanup()
            assert not old_lock.exists()


class TestHealthCheck:
    def test_health_check_good_syntax(self):
        from overlord import health_check
        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = Path(tmp)
            main_py = agent_dir / "main.py"
            main_py.write_text("x = 1\n")
            health_check(agent_dir, {})  # ska inte krascha

    def test_health_check_bad_syntax(self):
        from overlord import health_check
        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = Path(tmp)
            main_py = agent_dir / "main.py"
            main_py.write_text("def broken(\n")
            health_check(agent_dir, {})  # ska inte krascha, bara logga


class TestReadAgentConfig:
    def test_read_agent_config(self):
        from overlord import _read_agent_config
        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = Path(tmp) / "test-agent"
            agent_dir.mkdir(parents=True)
            (agent_dir / "agent.yaml").write_text("name: test\ncron: '* * * * *'\n")
            cfg = _read_agent_config(agent_dir)
            assert cfg is not None
            assert cfg.get("name") == "test"
