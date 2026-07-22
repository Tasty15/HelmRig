"""Delade verktyg för HelmRig — en gång, importerad överallt."""

import importlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

RTK = Path(os.path.expanduser("~/.local/bin/rtk"))
HEADROOM = Path(os.path.expanduser("~/.local/bin/headroom"))

_SENSITIVE_PATTERNS = [
    # OpenAI-kompatibla nycklar (sk-...)
    re.compile(r'((?:\w*[_-])?(?:api[_-]?key|apikey)\s*[=:]\s*)(sk-[a-zA-Z0-9]{10,})', re.IGNORECASE),
    # Alla *_KEY, *_SECRET, *_TOKEN, *_PASSWORD (fångar t.ex. DEEPSEEK_API_KEY)
    re.compile(r'((?:\w*[_-])?(?:key|secret|token|password)\s*[=:]\s*)(\S+)', re.IGNORECASE),
    # Bearer tokens i headers
    re.compile(r'(authorization:\s*)(bearer\s+\S+)', re.IGNORECASE),
]


def mask_secrets(text: str) -> str:
    """Maska API-nycklar, tokens och lösenord i en sträng.

    Ex: "KEY=sk-abc123..." → "KEY=sk-***"
    """
    if not text:
        return text
    for pat in _SENSITIVE_PATTERNS:
        text = pat.sub(r'\1***', text)
    return text


def rtk_compress(text: str) -> str:
    """Komprimera text genom rtk pipe — sparar tokens i LLM-kontext.

    Fallerar tyst till originaltext om rtk saknas eller timeout.
    """
    if not text or not RTK.exists():
        return text
    try:
        r = subprocess.run(
            [str(RTK), "pipe"], input=text,
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout if r.returncode == 0 and r.stdout else text
    except (subprocess.TimeoutExpired, OSError):
        return text


def headroom_memory(action: str, **kwargs) -> dict:
    """Headroom memory-operationer.

    Actions:
      list              — lista minnen (kwargs: agent, since, limit)
      show <id>         — visa specifikt minne (kwargs: id)
      save              — spara nytt minne (kwargs: agent, summary, tags)
      stats             — headroom memory stats
    """
    if not HEADROOM.exists():
        return {"error": "headroom not found — installera från headroom.dev"}

    if action == "list":
        limit = str(kwargs.get("limit", 5))
        since = kwargs.get("since", "7d")
        r = subprocess.run(
            [str(HEADROOM), "memory", "list", "--limit", limit, "--since", since],
            capture_output=True, text=True, timeout=10,
        )
        return {"stdout": r.stdout, "stderr": r.stderr, "rc": r.returncode}

    if action == "show":
        mid = kwargs.get("id")
        if not mid:
            return {"error": "id krävs för show"}
        r = subprocess.run(
            [str(HEADROOM), "memory", "show", mid, "--json"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout:
            try:
                return {"data": json.loads(r.stdout), "rc": 0}
            except json.JSONDecodeError:
                pass
        return {"error": r.stderr or "not found", "rc": r.returncode}

    if action == "save":
        # headroom saknar 'add' — spara via export→append→import
        agent = kwargs.get("agent", "unknown")
        summary = kwargs.get("summary", "")
        tags = kwargs.get("tags", [])
        r = subprocess.run(
            [str(HEADROOM), "memory", "export"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return {"error": "kunde inte exportera", "rc": r.returncode}
        try:
            memories = json.loads(r.stdout) if r.stdout.strip() else []
        except json.JSONDecodeError:
            memories = []
        now = datetime.now(timezone.utc).isoformat()
        new_mem = {
            "id": str(uuid.uuid4()),
            "content": json.dumps({"ts": now, "summary": summary, "tags": tags}),
            "user_id": "helmrig",
            "session_id": "",
            "agent_id": agent,
            "turn_id": None,
            "created_at": now,
            "valid_from": now,
            "valid_until": None,
            "importance": 0.5,
            "supersedes": None,
            "superseded_by": None,
            "promoted_from": None,
            "promotion_chain": [],
            "access_count": 0,
            "last_accessed": None,
            "entity_refs": [],
            "embedding": None,
            "metadata": {},
        }
        memories.append(new_mem)
        tmp = Path(f"/tmp/headroom-import-{agent}-{int(time.time())}.json")
        tmp.write_text(json.dumps(memories, indent=2))
        result = subprocess.run(
            [str(HEADROOM), "memory", "import", str(tmp), "-f"],
            capture_output=True, text=True, timeout=10,
        )
        tmp.unlink(missing_ok=True)
        if result.returncode == 0:
            return {"status": "ok", "id": new_mem["id"]}
        return {"error": result.stderr[:200], "rc": result.returncode}

    if action == "stats":
        r = subprocess.run(
            [str(HEADROOM), "memory", "stats"],
            capture_output=True, text=True, timeout=10,
        )
        return {"stdout": r.stdout, "rc": r.returncode}

    return {"error": f"unknown action: {action}"}


def load_env(agent_dir: Path) -> None:
    """Ladda .env från projektroten."""
    env_path = agent_dir.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def read_env_file(project_root: Path) -> dict:
    """Läs .env-fil som dict, exklusive kommentarer."""
    env_path = project_root / ".env"
    if not env_path.exists():
        return {}
    result = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def write_env_file(project_root: Path, env: dict) -> None:
    """Skriv .env-fil från dict, sorterad."""
    env_path = project_root / ".env"
    lines = [f"{k}={v}" for k, v in sorted(env.items())]
    env_path.write_text("\n".join(lines) + "\n")


def create_model(config: dict) -> object:
    """Skapa en LangChain-modell baserat på agent.yaml config.

    Stödjer: openai, deepseek, anthropic, gemini/google, ollama, openrouter,
    och alla OpenAI-kompatibla APIer (qwen, kimi m.fl. via generic_openai).

    Kräver att rätt langchain-paket är installerat per agent.
    """
    provider = (config.get("provider") or "openai").lower().replace("-", "_")
    model_name = config.get("name", "gpt-4o")
    api_base = config.get("api_base")
    api_key = os.environ.get(f"{provider.upper()}_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY", "")

    if provider in ("openai", "generic_openai"):
        from langchain_openai import ChatOpenAI
        kwargs = {"model": model_name, "api_key": api_key, "temperature": 0.7}
        if api_base:
            kwargs["base_url"] = api_base  # openai v1.x använder base_url
        return ChatOpenAI(**kwargs)

    if provider == "deepseek":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name, api_key=api_key,
            base_url=api_base or "https://api.deepseek.com/v1",
            temperature=0.7,
        )

    if provider in ("anthropic", "claude"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model_name, api_key=api_key, temperature=0.7)

    if provider in ("google", "gemini"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model_name, api_key=api_key, temperature=0.7)

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model_name, base_url=api_base or "http://localhost:11434", temperature=0.7)

    if provider in ("openrouter",):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name, api_key=api_key,
            base_url=api_base or "https://openrouter.ai/api/v1",
            temperature=0.7,
        )

    # Fallback: försök som OpenAI-kompatibel
    from langchain_openai import ChatOpenAI
    kwargs = {"model": model_name, "api_key": api_key, "temperature": 0.7}
    if api_base:
        kwargs["base_url"] = api_base
    return ChatOpenAI(**kwargs)


def call_skill(config: dict, name: str, **kwargs):
    """Ladda och kör en skill från agentens skills/-katalog.

    Om skill har ``sandbox: true`` körs den i subprocess med minimal miljö
    (endast PATH, HOME) för att API-nycklar inte ska läcka.
    """
    for skill in config.get("skills", []):
        if skill["name"] == name:
            sandbox = skill.get("sandbox", False)
            if sandbox:
                return _run_skill_sandboxed(skill, **kwargs)
            mod = importlib.import_module(skill["module"])
            return mod.run(**kwargs)
    raise ValueError(
        f"Skill '{name}' finns inte i agent.yaml. "
        f"Tillgängliga: {[s['name'] for s in config.get('skills', [])]}"
    )


def _run_skill_sandboxed(skill: dict, **kwargs) -> dict:
    """Kör en skill i subprocess med minimal miljö — API-nycklar läcker inte."""
    import json
    import subprocess as _subprocess

    clean_env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "/tmp")}
    mod_name = skill["module"]
    # ponytail: subprocess med --eval för att isolera miljön
    code = (
        f"import sys, json; sys.path.insert(0, '.'); "
        f"from {mod_name} import run; "
        f"print(json.dumps(run(**{json.dumps(kwargs)})))"
    )
    r = _subprocess.run(
        [sys.executable, "-c", code],
        env=clean_env, capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        return {"error": r.stderr[:200], "status": "error"}
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"error": "invalid sandbox output", "stdout": r.stdout[:200], "status": "error"}
