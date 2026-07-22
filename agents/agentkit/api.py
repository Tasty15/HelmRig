"""Programmatiskt API för HelmRig — skapa, kör och hantera agenter i kod."""

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

AGENTS_DIR = Path(__file__).parent.parent
VENV_PYTHON = AGENTS_DIR.parent / ".venv" / "bin" / "python3"


def _python(agent_dir: Path) -> str:
    """Hitta rätt python för en agent (per-agent venv > huvud-venv > system)."""
    agent_venv = agent_dir / ".venv" / "bin" / "python3"
    if agent_venv.exists():
        return str(agent_venv)
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return "python3"


def list_agents() -> list[dict]:
    """Lista alla agenter med deras konfiguration."""
    agents = []
    for d in sorted(AGENTS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        yaml_path = d / "agent.yaml"
        if not yaml_path.exists():
            continue
        try:
            cfg = yaml.safe_load(yaml_path.read_text())
            agents.append({
                "name": cfg.get("name", d.name),
                "dir": d.name,
                "cron": cfg.get("cron"),
                "skills": len(cfg.get("skills", [])),
                "model": cfg.get("model", {}).get("name", "?"),
            })
        except Exception:
            pass
    return agents


def get_agent(name: str) -> dict | None:
    """Hämta konfiguration för en specifik agent."""
    agent_dir = AGENTS_DIR / name
    yaml_path = agent_dir / "agent.yaml"
    if not yaml_path.exists():
        return None
    try:
        cfg = yaml.safe_load(yaml_path.read_text())
        return cfg
    except Exception:
        return None


def run_agent(name: str, timeout: int = 300, dry_run: bool = False) -> dict:
    """Kör en agent och returnera resultatet.

    Args:
        name: Agentnamn (mappnamn)
        timeout: Max exekveringstid i sekunder
        dry_run: Kör utan side-effects

    Returns:
        Dict med stdout, stderr, returncode, duration_s
    """
    import time
    from datetime import datetime, timezone

    agent_dir = AGENTS_DIR / name
    main_py = agent_dir / "main.py"
    if not main_py.exists():
        return {"error": f"Agent '{name}' saknar main.py", "returncode": 1}

    python = _python(agent_dir)
    env = os.environ.copy()
    if dry_run:
        env["HARNESS_DRY_RUN"] = "true"

    start = time.time()
    try:
        r = subprocess.run(
            [python, str(main_py)], env=env,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "error": f"timeout ({timeout}s)", "returncode": -1,
            "stdout": "", "stderr": "", "duration_s": timeout,
        }

    return {
        "returncode": r.returncode,
        "stdout": r.stdout,
        "stderr": r.stderr,
        "duration_s": round(time.time() - start, 2),
    }


def scaffold_agent(name: str, react: bool = False) -> dict:
    """Skapa en ny agent programmatiskt (motsvarar 'harness scaffold')."""
    agent_dir = AGENTS_DIR / name
    if agent_dir.exists():
        return {"error": f"Agent '{name}' finns redan"}

    agent_dir.mkdir(parents=False)
    (agent_dir / "skills").mkdir()
    (agent_dir / "skills" / "__init__.py").touch()
    (agent_dir / "skills" / "example_skill.py").write_text(
        '"""Exempelskills — ersätt med faktisk implementation."""\n\n\ndef run(**kwargs) -> dict:\n    return {"status": "ok", "result": "placeholder"}\n'
    )

    agent_yaml = f"""\
name: "{name}"
description: "Beskrivning av agenten"
instructions: |
  Du är en hjälpsam AI-assistent. Var koncis och saklig.
model:
  provider: openai
  name: gpt-4o
  api_base: https://api.openai.com/v1
skills:
  - name: example_skill
    module: skills.example_skill
    description: "Exempelskills"
    side_effect: false
cron: null
"""
    (agent_dir / "agent.yaml").write_text(agent_yaml)

    if react:
        main_py = '''\
"""Agent: {name} — ReAct (LLM väljer tools)."""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import yaml
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
AGENT_DIR = Path(__file__).parent
AGENT_CONFIG = yaml.safe_load((AGENT_DIR / "agent.yaml").read_text())
_skills = AGENT_CONFIG.get("skills", [])
for _s in _skills:
    mod = __import__(_s["module"], fromlist=["run"])
    wrapped = tool(mod.run, name=_s["name"], description=_s.get("description", _s["name"]))
    locals()[_s["name"]] = wrapped
tools = [locals()[s["name"]] for s in _skills]
model = ChatOpenAI(
    model=AGENT_CONFIG["model"]["name"],
    openai_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
    openai_api_base=AGENT_CONFIG["model"].get("api_base", "https://api.deepseek.com/v1"),
)
agent = create_react_agent(model, tools)
def run(inputs=None):
    return agent.invoke({"messages": inputs.get("messages", [])})
if __name__ == "__main__":
    system_msg = {"role": "system", "content": AGENT_CONFIG.get("instructions", "")}
    result = run({"messages": [system_msg]})
'''.format(name=name)
    else:
        main_py = '''\
"""Agent: {name}"""
import os, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import yaml
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict
from agentkit.utils import call_skill, load_env
AGENT_DIR = Path(__file__).parent
AGENT_CONFIG = yaml.safe_load((AGENT_DIR / "agent.yaml").read_text())
load_env(AGENT_DIR)
class AgentState(TypedDict):
    messages: list
def entry_node(state: AgentState) -> AgentState:
    return {"messages": state.get("messages", []) + ["Agenten startade"]}
builder = StateGraph(AgentState)
builder.add_node("entry", entry_node)
builder.add_edge(START, "entry")
builder.add_edge("entry", END)
graph = builder.compile()
def run(inputs=None):
    return graph.invoke(inputs or {"messages": []})
if __name__ == "__main__":
    result = run()
'''.format(name=name)

    (agent_dir / "main.py").write_text(main_py)
    (agent_dir / "requirements.txt").write_text(
        "langgraph>=0.3.0\nlangchain-core>=0.3.0\nlangchain-openai>=0.3.0\npyyaml>=6.0\n"
    )

    return {"status": "ok", "dir": str(agent_dir)}


def get_logs(agent: str | None = None, n: int = 10) -> list[dict]:
    """Hämta loggar för en eller alla agenter."""
    log_dir = AGENTS_DIR / ".overlord" / "logs"
    if not log_dir.exists():
        return []
    entries = []
    if agent:
        log_file = log_dir / f"{agent}.jsonl"
        if log_file.exists():
            for line in log_file.read_text().splitlines():
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    else:
        for f in sorted(log_dir.glob("*.jsonl")):
            for line in f.read_text().splitlines():
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return entries[-n:]
