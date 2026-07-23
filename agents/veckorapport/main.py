"""Agent: veckorapport — analysera veckans loggar och mejla rapport"""

import json, os, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import yaml
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

from agentkit.utils import load_env
from agentkit.memory import store as memory_store

AGENT_DIR = Path(__file__).parent
AGENT_CONFIG = yaml.safe_load((AGENT_DIR / "agent.yaml").read_text())
AGENT_NAME = AGENT_CONFIG["name"]
load_env(AGENT_DIR)
TO = os.environ.get("ALERT_EMAIL_TO", "grahn.simon@outlook.com")
LOG_DIR = Path(__file__).parent.parent / ".overlord" / "logs"


class AgentState(TypedDict):
    raw_logs: str
    report: str


def fetch_logs(state: AgentState) -> AgentState:
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    entries = []
    if LOG_DIR.exists():
        for f in sorted(LOG_DIR.glob("*.jsonl"), reverse=True)[:20]:
            for line in f.read_text().splitlines():
                try:
                    e = json.loads(line)
                    ts = e.get("ts", "")
                    if ts >= week_ago:
                        entries.append(e)
                except json.JSONDecodeError:
                    pass
    if not entries:
        return {"raw_logs": "Inga loggar från senaste veckan.", "report": ""}

    lines = []
    for e in entries[:50]:
        lines.append(
            f"[{e.get('ts','?')}] {e.get('agent','?')} | "
            f"{e.get('status','?')} | {e.get('duration_s',0):.1f}s | "
            f"tokens={e.get('tokens',0)} | {e.get('error','')}"
        )
    return {"raw_logs": "\n".join(lines), "report": ""}


def analyze(state: AgentState) -> AgentState:
    from agentkit.utils import create_model
    llm = create_model(AGENT_CONFIG.get("model", {}))
    prompt = (
        "Analysera veckans loggar från HelmRig AI-agenter. Rapportera:\n"
        "1. Mest körda agenter\n"
        "2. Vanligaste felen\n"
        "3. Total tokenförbrukning (summera tokens-fältet)\n"
        "4. Genomsnittlig körtid\n"
        "Skriv koncist på svenska.\n\n"
        f"{str(state['raw_logs'])[:6000]}"
    )
    report = llm.invoke(prompt).content
    return {"raw_logs": state["raw_logs"], "report": report}


def store_and_send(state: AgentState) -> AgentState:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    memory_store(AGENT_NAME, 'store:' + today, f"Veckorapport {today}: {str(state['report'])[:500]}", {"date": today})
    body = f"📊 Veckorapport — v. {today}\n{'='*40}\n\n{state['report']}"
    import subprocess
    week = datetime.now(timezone.utc).strftime("%V")
    subprocess.run(
        ["composio", "execute", "GMAIL_SEND_EMAIL", "-d",
         json.dumps({"recipient_email": TO, "subject": f"📊 Veckorapport v.{week}", "body": body})],
        capture_output=True, text=True, timeout=30,
    )
    return state


builder = StateGraph(AgentState)
builder.add_node("fetch", fetch_logs)
builder.add_node("analyze", analyze)
builder.add_node("store_and_send", store_and_send)
builder.add_edge(START, "fetch")
builder.add_edge("fetch", "analyze")
builder.add_edge("analyze", "store_and_send")
builder.add_edge("store_and_send", END)
graph = builder.compile()


def run(inputs: dict | None = None) -> dict:
    return graph.invoke(inputs or {})


if __name__ == "__main__":
    result = run()
    print(result.get("report", ""))
