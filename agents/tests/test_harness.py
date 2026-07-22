"""Tester för harness CLI-kommandon."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

HARNESS = Path(__file__).parent.parent / "harness.py"
VENV_PY = Path(__file__).parent.parent.parent / ".venv" / "bin" / "python3"
PYTHON = str(VENV_PY) if VENV_PY.exists() else sys.executable


def _run(args: list[str]) -> subprocess.CompletedProcess:
    """Kör harness med givna argument."""
    return subprocess.run(
        [PYTHON, str(HARNESS)] + args,
        capture_output=True, text=True,
        cwd=HARNESS.parent,
    )


class TestHarnessCLI:
    def test_list_empty(self):
        """'harness list' visar meddelande om inga agenter."""
        r = _run(["list"])
        assert r.returncode == 0

    def test_help(self):
        """'harness --help' visar hjälp."""
        r = _run(["--help"])
        assert r.returncode == 0
        assert "scaffold" in r.stdout

    def test_scaffold_invalid_name(self):
        """'harness scaffold' med ogiltigt namn ska misslyckas."""
        r = _run(["scaffold", "hej med mellanslag"])
        assert r.returncode != 0

    def test_scaffold_valid_name(self):
        """'harness scaffold' med giltigt namn skapar mappstruktur."""
        name = "test-unit-agent"
        try:
            r = _run(["scaffold", name])
            assert r.returncode == 0
            agent_dir = Path(HARNESS).parent / name
            assert agent_dir.exists()
            assert (agent_dir / "agent.yaml").exists()
            assert (agent_dir / "main.py").exists()
            assert (agent_dir / "skills").exists()
            assert (agent_dir / "requirements.txt").exists()
        finally:
            # Cleanup
            import shutil
            shutil.rmtree(Path(HARNESS).parent / name, ignore_errors=True)

    def test_scaffold_react(self):
        """'harness scaffold --react' skapar ReAct-agent."""
        name = "test-react-unit"
        try:
            r = _run(["scaffold", name, "--react"])
            assert r.returncode == 0
            agent_dir = Path(HARNESS).parent / name
            content = (agent_dir / "main.py").read_text()
            assert "create_react_agent" in content
        finally:
            import shutil
            shutil.rmtree(Path(HARNESS).parent / name, ignore_errors=True)

    def test_validate_ok(self):
        """'harness validate' på en agent som har agent.yaml."""
        name = "test-valid-unit"
        try:
            _run(["scaffold", name])
            r = _run(["validate", name])
            assert r.returncode == 0
        finally:
            import shutil
            shutil.rmtree(Path(HARNESS).parent / name, ignore_errors=True)


class TestHarnessHelpers:
    def test_validate_name_good(self):
        """_validate_name godkänner giltiga namn."""
        _run(["scaffold", "good-name"])

        import shutil
        shutil.rmtree(Path(HARNESS).parent / "good-name", ignore_errors=True)

    def test_validate_name_bad(self):
        """_validate_name avvisar ogiltiga namn."""
        r = _run(["scaffold", "START_WITH_UPPER"])
        assert r.returncode != 0
        r = _run(["scaffold", "../../../etc"])
        assert r.returncode != 0
