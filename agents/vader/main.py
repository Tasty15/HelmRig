"""Agent: vader — hämta väder, föreslå klädsel, mejla"""

import json, os, sys, urllib.request
from datetime import date
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

# wttr.in — enkel väder-API, inget API-nyckel krävs
WEATHER_URL = "https://wttr.in/Stockholm?format=%C+%t+%w+%p&amp;lang=sv"


class AgentState(TypedDict):
    weather_data: str
    suggestion: str


def fetch_weather(state: AgentState) -> AgentState:
    print(f"  🌤️ Hämtar väder från wttr.in...")
    try:
        r = urllib.request.urlopen("https://wttr.in/Stockholm?format=%25C+%25t+%25w+%25p&lang=sv", timeout=10)
        weather = r.read().decode().strip()
        print(f"  🌡️ {weather}")
    except Exception as e:
        weather = ""
    return {"weather_data": weather or "Inget väder kunde hämtas.", "suggestion": ""}


def suggest(state: AgentState) -> AgentState:
    from agentkit.utils import create_model
    llm = create_model(AGENT_CONFIG.get("model", {}))
    prompt = (
        "Givet följande väderdata för Stockholm, föreslå en lämplig "
        "klädsel för dagen. Var praktisk. Skriv på svenska.\n\n"
        f"Väder: {str(state['weather_data'])[:500]}"
    )
    suggestion = llm.invoke(prompt).content
    return {"weather_data": state["weather_data"], "suggestion": suggestion}


def store_and_send(state: AgentState) -> AgentState:
    today = date.today().isoformat()
    memory_store(AGENT_NAME, 'store:' + str(date.today()), f"Väder {today}: {str(state['suggestion'])[:300]}", {"date": today})
    body = f"🌤️ Dagens väder — {today}\n{'='*40}\n\n{state['suggestion']}"
    import subprocess
    subprocess.run(
        ["composio", "execute", "GMAIL_SEND_EMAIL", "-d",
         json.dumps({"recipient_email": TO, "subject": f"🌤️ Väder {today}", "body": body})],
        capture_output=True, text=True, timeout=30,
    )
    return state


builder = StateGraph(AgentState)
builder.add_node("fetch", fetch_weather)
builder.add_node("suggest", suggest)
builder.add_node("store_and_send", store_and_send)
builder.add_edge(START, "fetch")
builder.add_edge("fetch", "suggest")
builder.add_edge("suggest", "store_and_send")
builder.add_edge("store_and_send", END)
graph = builder.compile()


def run(inputs: dict | None = None) -> dict:
    return graph.invoke(inputs or {})


if __name__ == "__main__":
    result = run()
    print(result.get("suggestion", ""))
