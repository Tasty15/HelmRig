"""Knowledge base — auto-index agent-resultat i Chroma.

Används av harness.py efter varje agentkörning för att spara resultatet.
Ger agenter möjlighet att söka i tidigare körningars output.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from agentkit.memory import recall as _recall, store as _store


def store_result(agent: str, status: str, output: str, metadata: dict = None) -> dict:
    """Spara en agentkörning i knowledge base.

    Anropas automatiskt efter varje agentkörning (via harness.py).

    Args:
        agent: Agentnamn
        status: "ok" eller "error"
        output: Agentens stdout-output (komprimeras automatiskt)
        metadata: Extra metadata (t.ex. {"cron": "0 9 * * 1-5", "duration_s": 12.5})

    Returns:
        Dict med status och id
    """
    ts = datetime.now(timezone.utc).isoformat()
    meta = {
        "agent": agent,
        "ts": ts,
        "status": status,
    }
    if metadata:
        # ponytail: max 5 extra metadata-nycklar
        for k, v in list(metadata.items())[:5]:
            if isinstance(v, (str, int, float, bool)):
                meta[k] = str(v)

    # Key = timestamp för unik sortering
    key = f"run:{ts}"

    # Extrahera CHAIN_OUTPUT: om det finns — indexera separat
    for line in output.splitlines():
        if line.startswith("CHAIN_OUTPUT:"):
            try:
                chain_data = json.loads(line[len("CHAIN_OUTPUT:"):])
                meta["has_chain_output"] = "true"
                _store(agent, f"chain:{ts}", json.dumps(chain_data, ensure_ascii=False), {"agent": agent, "type": "chain_output", "ts": ts})
            except json.JSONDecodeError:
                pass
            break

    return _store(agent, key, output, meta)


def search(agent: str = None, query: str = "", limit: int = 3) -> list[dict]:
    """Sök i knowledge base över agentkörningar.

    Args:
        agent: Agentnamn (None = sök i alla agenter)
        query: Sökfråga (tom = senaste resultaten)
        limit: Max resultat (default 3)

    Returns:
        Lista med {"id": str, "content": str, "metadata": dict}
    """
    if agent:
        return _recall(agent, query, limit=limit)

    # Sök i alla agenter
    import chromadb
    from pathlib import Path
    CHROMA_DIR = Path(__file__).parent / ".chroma"
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    results = []
    collections = client.list_collections()
    for col in collections:
        name = col.name
        if not name.startswith("helmrig_"):
            continue
        agent_name = name[len("helmrig_"):]
        items = _recall(agent_name, query, limit=limit)
        results.extend(items)

    # Sortera på distance (om sökning) eller id (om senaste)
    if query:
        results.sort(key=lambda x: x.get("distance") or 999)
    return results[:limit]
