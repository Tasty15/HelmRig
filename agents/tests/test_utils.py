"""Tester för agentkit/utils.py"""

import os
import tempfile
from pathlib import Path

import pytest

from agentkit.utils import call_skill, load_env


class TestLoadEnv:
    # load_env letar efter .env i agent_dir.parent.parent (ai/ level)
    # Ex: agent_dir = ai/agents/stock-watcher → .env vid ai/.env
    # Miljövariabler kan läcka mellan tester, så prefixa unikt.

    def _make_agent_dir(self, root: Path) -> Path:
        d = root / "agents" / "test-agent"
        d.mkdir(parents=True)
        return d

    def test_load_env_basic(self):
        """Ladda .env med nyckel=värdepar."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_dir = self._make_agent_dir(root)
            (root / ".env").write_text("LOADENV_KEY1=value\nFOO=bar\n")
            load_env(agent_dir)
            assert os.environ.get("LOADENV_KEY1") == "value"

    def test_load_env_skips_comments(self):
        """Hoppa över kommentarsrader."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_dir = self._make_agent_dir(root)
            (root / ".env").write_text("# comment\nLOADENV_KEY2=val\n")
            load_env(agent_dir)
            assert os.environ.get("LOADENV_KEY2") == "val"

    def test_load_env_no_file(self):
        """Inget fel om .env saknas."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_dir = self._make_agent_dir(root)
            load_env(agent_dir)  # ska inte krascha

