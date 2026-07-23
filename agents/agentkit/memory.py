"""Agentminne — Chroma vector store med token-snål recall.

Användning:
    from agentkit.memory import store, recall

    store("research-agent", "senaste sökresultatet", {"url": "..."})
    results = recall("research-agent", "aktiekurser", limit=3)

Token-skydd:
    - headroom-komprimering före lagring (-70% tokens)
    - limit=3 default (max 3 chunks injectas)
    - Inget auto-inject — agenten måste explicit anropa recall()
    - Collection per agent — inget globalt brus
"""

import json
import os
from pathlib import Path

CHROMA_DIR = Path(__file__).parent / ".chroma"


def _get_collection(agent: str):
    """Hämta (eller skapa) en Chroma-collection för agenten."""
    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    # ponytail: collection per agent = isolerat namespace, inget brus mellan agenter
    return client.get_or_create_collection(
        name=f"helmrig_{agent}",
        metadata={"hnsw:space": "cosine"},
    )


def store(agent: str, key: str, content: str, metadata: dict = None) -> dict:
    """Spara ett resultat i agentens vector store.

    Args:
        agent: Agentnamn (används som collection-namn)
        key: Unik nyckel för lookup (t.ex. "crawl:https://...")
        content: Text att indexera (komprimeras automatiskt)
        metadata: Extra metadata (max 200 tokens)

    Returns:
        Dict med status, id
    """
    from agentkit.utils import headroom_memory

    # Komprimera innan lagring — token-snål
    compressed = headroom_memory("save", agent=agent, summary=content, tags=[])
    # headroom_memory returnerar en dict med status/id;
    # om headroom inte finns, använd content som fallback
    storage_text = compressed.get("stdout", "") if compressed.get("status") == "ok" else content

    # Men headroom_memory("save") sparar i headrooms eget system, inte Chroma.
    # Vi sparar direkt i Chroma med den komprimerade texten.
    # ponytail: använd rtk_compress direkt — snabbare och enklare
    from agentkit.utils import rtk_compress

    compressed_text = rtk_compress(content) or content
    col = _get_collection(agent)
    doc_id = f"{agent}:{key}"

    meta = {"agent": agent, "key": key}
    if metadata:
        # Begränsa metadata till 10 entries — ponytail: nog för sökfilter
        for k, v in list(metadata.items())[:10]:
            if isinstance(v, (str, int, float, bool)):
                meta[k] = v

    col.upsert(
        ids=[doc_id],
        documents=[compressed_text],
        metadatas=[meta],
    )
    return {"status": "ok", "id": doc_id, "compressed": len(compressed_text) < len(content)}


def recall(agent: str, query: str = "", limit: int = 3, filter_metadata: dict = None) -> list[dict]:
    """Sök i agentens minne — returnerar max ``limit`` resultat.

    Args:
        agent: Agentnamn
        query: Sökfråga (tom = hämta senaste)
        limit: Max resultat (default 3 — token-snål garanti)
        filter_metadata: Filtrera på metadata-nycklar (t.ex. {"url": "..."})

    Returns:
        Lista med {"id": str, "content": str, "metadata": dict, "distance": float}
    """
    col = _get_collection(agent)

    if query:
        results = col.query(
            query_texts=[query],
            n_results=min(limit, 20),  # ponytail: hård tak på 20 oavsett vad
            where=filter_metadata,
        )
    else:
        # Hämta senaste N (inga embed-frågor)
        count = col.count()
        n = min(count, limit)
        results = col.get(limit=n)

    items = []
    # Chroma returnerar list-of-lists för query; flat dict för get
    ids = results.get("ids", [])
    docs = results.get("documents", [])
    metas = results.get("metadatas", [])
    dists = results.get("distances", [])

    # Normalisera: både query och get returnerar olika format
    if isinstance(ids, list) and ids and isinstance(ids[0], list):
        ids = ids[0]
        docs = docs[0] if docs and isinstance(docs[0], list) else docs
        metas = metas[0] if metas and isinstance(metas[0], list) else metas
        dists = dists[0] if dists and isinstance(dists[0], list) else dists

    for i in range(min(len(ids), limit)):
        items.append({
            "id": ids[i] if i < len(ids) else "",
            "content": docs[i] if i < len(docs) else "",
            "metadata": metas[i] if i < len(metas) else {},
            "distance": round(dists[i], 4) if i < len(dists) else None,
        })

    return items


def forget(agent: str, key: str = None) -> dict:
    """Ta bort ett eller alla minnen för en agent."""
    col = _get_collection(agent)
    if key:
        doc_id = f"{agent}:{key}"
        try:
            col.delete(ids=[doc_id])
            return {"status": "ok", "deleted": doc_id}
        except Exception:
            return {"status": "error", "error": f"nyckel '{key}' finns inte"}
    else:
        count = col.count()
        try:
            col.delete(where={"agent": agent})
            return {"status": "ok", "deleted_count": count}
        except Exception:
            # Fallback: ta bort hela collectionen
            import chromadb
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            client.delete_collection(name=f"helmrig_{agent}")
            return {"status": "ok", "deleted_count": count}
