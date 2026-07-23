"""Agent: restaurang — crawla lunchmenyer, spara i Chroma, mejla"""

import asyncio, json, os, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import yaml
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

from agentkit.utils import load_env
from agentkit.crawler import crawl
from agentkit.memory import store as memory_store

AGENT_DIR = Path(__file__).parent
AGENT_CONFIG = yaml.safe_load((AGENT_DIR / "agent.yaml").read_text())
AGENT_NAME = AGENT_CONFIG["name"]
load_env(AGENT_DIR)
TO = os.environ.get("ALERT_EMAIL_TO", "grahn.simon@outlook.com")


class AgentState(TypedDict):
    raw: str
    menu_text: str


def fetch_menus(state: AgentState) -> AgentState:
    async def _crawl_all():
        texts = []
        for url in [
    "https://www.koket.se/recept",
    "https://www.ica.se/recept/",
        ]:
            print(f"  🍽️ Crawlar {url}...")
            r = await crawl(url, max_chars=2000)
            if r.get("status") == "ok":
                texts.append(f"### {url}\n{r.get('content','')[:2000]}")
        return "\n\n".join(texts) if texts else "Kunde inte hämta menyer."
    raw = asyncio.run(_crawl_all())
    return {"raw": raw, "menu_text": ""}


def summarize(state: AgentState) -> AgentState:
    from agentkit.utils import create_model
    llm = create_model(AGENT_CONFIG.get("model", {}))
    prompt = (
        "Extrahera ett eller två intressanta recept från nedanstående "
        "recept-sajter. Namnge rätten, lista huvudingredienserna och "
        "uppskatta tillagningstid. Markera vegetariska med 🌱. "
        "Skriv på svenska.\n\n"
        f"{state['raw'][:4000]}"
    )
    menu_text = llm.invoke(prompt).content
    return {"raw": state["raw"], "menu_text": menu_text}


def store_and_send(state: AgentState) -> AgentState:
    today = date.today().isoformat()
    memory_store(AGENT_NAME, 'store:' + str(date.today()), f"Dagens recept {today}: {str(state['menu_text'])[:500]}", {"date": today})
    body = f"🍽️ Dagens matinspiration — {today}\n{'='*40}\n\n{str(state['menu_text'])}"
    import subprocess
    subprocess.run(
        ["composio", "execute", "GMAIL_SEND_EMAIL", "-d",
         json.dumps({"recipient_email": TO, "subject": f"🍽️ Lunch {today}", "body": body})],
        capture_output=True, text=True, timeout=30,
    )
    return state


builder = StateGraph(AgentState)
builder.add_node("fetch", fetch_menus)
builder.add_node("summarize", summarize)
builder.add_node("store_and_send", store_and_send)
builder.add_edge(START, "fetch")
builder.add_edge("fetch", "summarize")
builder.add_edge("summarize", "store_and_send")
builder.add_edge("store_and_send", END)
graph = builder.compile()


def run(inputs: dict | None = None) -> dict:
    return graph.invoke(inputs or {})


if __name__ == "__main__":
    result = run()
    print(result.get("menu_text", ""))
