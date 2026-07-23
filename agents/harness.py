#!/usr/bin/env python3
"""HelmRig Harness — scaffold, run, and schedule agents."""

import argparse
import importlib.util
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from agentkit.utils import rtk_compress, headroom_memory

AGENTS_DIR = Path(__file__).parent
OVERLORD_DIR = AGENTS_DIR / ".overlord"
VENV_PYTHON = AGENTS_DIR.parent / ".venv" / "bin" / "python3"


# ── Templates ──────────────────────────────────────────────────────────

AGENT_YAML_TEMPLATE = '''\
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
cron: null  # "0 9 * * 1-5" för vardagar 09:00
'''

MAIN_PY_TEMPLATE = '''\
"""Agent: {name}"""

import json
import sys
from pathlib import Path

import yaml
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

sys.path.insert(0, str(Path(__file__).parent))

from agentkit.utils import call_skill, headroom_memory, load_env


# ── Config ─────────────────────────────────────────────────────────────
AGENT_DIR = Path(__file__).parent
AGENT_CONFIG = yaml.safe_load((AGENT_DIR / "agent.yaml").read_text())
load_env(AGENT_DIR)


# ── Context från headroom (tidigare körningar) ─────────────────────────
_AGENT_NAME = AGENT_CONFIG.get("name", AGENT_DIR.name)
_context = headroom_memory("list", agent=_AGENT_NAME, limit=3, since="7d")
if _context.get("stdout"):
    print(f"📚 context: {{len(_context['stdout'].splitlines())}} rader headroom-minnen")


class AgentState(TypedDict):
    messages: list


def entry_node(state: AgentState) -> AgentState:
    return {{"messages": state.get("messages", []) + ["Agenten startade"]}}


builder = StateGraph(AgentState)
builder.add_node("entry", entry_node)
builder.add_edge(START, "entry")
builder.add_edge("entry", END)
graph = builder.compile()


def run(inputs: dict | None = None) -> dict:
    return graph.invoke(inputs or {{"messages": []}})


if __name__ == "__main__":
    result = run()
'''

REACT_MAIN_PY_TEMPLATE = '''\
"""Agent: {name} — ReAct (LLM väljer tools)."""

import json
import sys
from pathlib import Path

import yaml
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

sys.path.insert(0, str(Path(__file__).parent))

from agentkit.utils import create_model, headroom_memory, load_env


# ── Config ─────────────────────────────────────────────────────────────
AGENT_DIR = Path(__file__).parent
AGENT_CONFIG = yaml.safe_load((AGENT_DIR / "agent.yaml").read_text())
load_env(AGENT_DIR)


# ── Context från headroom (tidigare körningar) ─────────────────────────
_AGENT_NAME = AGENT_CONFIG.get("name", AGENT_DIR.name)
_context = headroom_memory("list", agent=_AGENT_NAME, limit=3, since="7d")
if _context.get("stdout"):
    print(f"📚 context: {{len(_context['stdout'].splitlines())}} rader headroom-minnen")


# ── Build tools from skills ────────────────────────────────────────────
_skills = AGENT_CONFIG.get("skills", [])

for _s in _skills:
    mod = __import__(_s["module"], fromlist=["run"])
    fn = mod.run
    name = _s["name"]
    desc = _s.get("description", name)

    # Dekorera fn som @tool (docstring blir LLM-schema)
    wrapped = tool(fn, name=name, description=desc)
    locals()[name] = wrapped

tools = [locals()[s["name"]] for s in _skills]


# ── Model (väljer automatiskt provider via create_model) ───────────────
model = create_model(AGENT_CONFIG.get("model", {{}}))

agent = create_react_agent(model, tools)


def run(inputs: dict | None = None) -> dict:
    """Kör agenten med givna meddelanden. LLM väljer tools under tiden."""
    return agent.invoke({{"messages": inputs.get("messages", [])}})


if __name__ == "__main__":
    system_msg = {{"role": "system", "content": AGENT_CONFIG.get("instructions", "")}}
    result = run({{"messages": [system_msg]}})
    for m in result.get("messages", []):
        if hasattr(m, "content") and m.content:
            print(m.content)
'''


REQUIREMENTS_TEMPLATE = '''\
langgraph>=0.3.0
langchain-core>=0.3.0
langchain-openai>=0.3.0
pyyaml>=6.0
# === Välj din AI-leverantör (lägg till en rad) ===
# langchain-anthropic     # Anthropic Claude
# langchain-google-genai  # Google Gemini
# langchain-ollama        # Lokala modeller (Ollama)
# === App-integrationer (Composio) ===
# composio-core            # Gmail, Google Sheets, Slack, GitHub m.fl.
# Sedan: composio add gmail  för att koppla ditt Google-konto
'''


# ── Helpers ────────────────────────────────────────────────────────────

def _read_config(agent_dir: Path) -> dict | None:
    """Läs och validera agent.yaml."""
    yaml_path = agent_dir / "agent.yaml"
    if not yaml_path.exists():
        print(f"❌ Ingen agent.yaml i {agent_dir}")
        return None
    try:
        cfg = yaml.safe_load(yaml_path.read_text())
    except Exception as e:
        print(f"❌ agent.yaml parse-fel: {e}")
        return None
    if "name" not in cfg:
        print(f"❌ agent.yaml saknar 'name'")
        return None
    if "model" not in cfg:
        print(f"⚠️  agent.yaml saknar 'model' — använder default")
        cfg["model"] = {"provider": "openai", "name": "gpt-4o"}

    # Merge overlord-config
    overlord = _load_overlord_config()

    # Applicera defaults
    defaults = overlord.get("defaults", {})
    for key, val in defaults.items():
        if key not in cfg or cfg[key] is None:
            cfg[key] = val
        elif isinstance(val, dict) and isinstance(cfg.get(key), dict):
            for sub_key, sub_val in val.items():
                if sub_key not in cfg[key]:
                    cfg[key][sub_key] = sub_val

    # Applicera overrides
    overrides = overlord.get("overrides", {}).get(agent_dir.name, {})
    for key, val in overrides.items():
        cfg[key] = val

    return cfg


def _load_overlord_config() -> dict:
    """Läs central config från .overlord/config.yaml. Tom dict om ingen config finns."""
    config_path = OVERLORD_DIR / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        return yaml.safe_load(config_path.read_text()) or {}
    except Exception as e:
        print(f"⚠️  config.yaml parse-fel: {e}")
        return {}


def _validate_name(name: str) -> str:
    """Validera agentnamn — endast [a-z0-9_-]. Höj vid ogiltigt."""
    if not re.match(r'^[a-z0-9][a-z0-9_-]{0,63}$', name):
        print(f"❌ Ogiltigt namn '{name}'. Använd endast [a-z0-9_-], max 64 tecken, börjar med bokstav/siffra.")
        sys.exit(1)
    return name


def _mask_secrets_in_dict(d: dict) -> dict:
    """Maska känslig data i en dict via JSON-roundtrip."""
    from agentkit.utils import mask_secrets
    return json.loads(mask_secrets(json.dumps(d, ensure_ascii=False)))


def _get_git_hash() -> str | None:
    """Hämta kort git-hash för commit-spårning i loggar."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=AGENTS_DIR,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return None


def _write_log_entry(entry: dict) -> None:
    """Skriv en loggpost till JSONL (maskar API-nycklar)."""
    log_dir = OVERLORD_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{entry['agent']}.jsonl"
    # Maska känslig data innan lagring
    safe_entry = _mask_secrets_in_dict(entry)
    with open(log_file, "a") as f:
        f.write(json.dumps(safe_entry, ensure_ascii=False) + "\n")


def _alert_on_failure(agent: str, error: str, log_entry: dict) -> None:
    """Skicka alert om en agent misslyckas (om ALERT_EMAIL_TO är satt)."""
    if not os.environ.get("ALERT_EMAIL_TO"):
        return
    try:
        from agentkit.alert import send_email_alert
        r = send_email_alert(agent, error, log_entry)
        if r.get("status") == "error":
            print(f"⚠️  Alert misslyckades: {r.get('detail', '?')}", file=sys.stderr)
    except Exception as e:
        print(f"⚠️  Alert error: {e}", file=sys.stderr)


def _check_deps(agent_dir: Path) -> bool:
    """Kontrollera att packages i requirements.txt finns installerade."""
    reqs_path = agent_dir / "requirements.txt"
    if not reqs_path.exists():
        return True
    ok = True
    for line in reqs_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split(">=")[0].split("==")[0].split("<")[0].strip()
        # Hantera pip-paketnamn som skiljer sig från importnamn
        import_name = name.replace("-", "_").replace(".", "_")
        if import_name in sys.stdlib_module_names:
            continue
        try:
            importlib.util.find_spec(import_name)
        except ModuleNotFoundError:
            print(f"⚠️  Saknas: '{name}' — kör: pip install {name}")
            ok = False
    if not ok:
        print(f"💡 Installera alla med: {VENV_PYTHON} -m pip install -r {reqs_path}")
    return ok


# ── Commands ───────────────────────────────────────────────────────────

def _list_agents() -> list[Path]:
    """Hitta alla agentkataloger med agent.yaml."""
    agents = []
    for d in sorted(AGENTS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        if (d / "agent.yaml").exists():
            agents.append(d)
    return agents


def cmd_list(args: argparse.Namespace) -> None:
    """Lista alla agenter med status."""
    agents = _list_agents()
    if not agents:
        print("🤷 Inga agenter hittades.")
        return

    # Samla senaste status från loggar
    log_dir = OVERLORD_DIR / "logs"
    statuses = {}
    if log_dir.exists():
        for f in log_dir.glob("*.jsonl"):
            lines = f.read_text().splitlines()
            if lines:
                try:
                    statuses[f.stem] = json.loads(lines[-1])
                except json.JSONDecodeError:
                    pass

    print(f"{'Agent':22s} {'Status':7s} {'Senast':20s} {'Cron':22s} {'Skills':s}")
    print("-" * 85)
    for d in agents:
        cfg = _read_config(d)
        if cfg is None:
            continue
        name = cfg.get("name", d.name)
        cron = cfg.get("cron", "—") or "—"
        n_skills = len(cfg.get("skills", []))
        e = statuses.get(name, {})
        icon = "✅" if e.get("status") == "ok" else ("❌" if e.get("status") == "error" else "💤")
        ts = e.get("ts", "aldrig")[:16]
        status = e.get("status", "never")
        print(f"{icon} {name:20s} {status:7s} {ts:20s} {cron:22s} {n_skills} skills")

    print(f"\n{len(agents)} agent(er)")


def _ensure_agent_venv(agent_dir: Path) -> str:
    """Skapa per-agent virtualenv om den inte finns. Returnera python-sökväg."""
    venv_dir = agent_dir / ".venv"
    bin_dir = venv_dir / "bin"
    python_path = bin_dir / "python3"
    if python_path.exists():
        return str(python_path)
    print(f"   🔧 Skapar per-agent venv för {agent_dir.name}...")
    r = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        print(f"   ⚠️  Kunde inte skapa venv: {r.stderr[:200]}, fallerar till huvud-venv")
        return str(VENV_PYTHON) if VENV_PYTHON.exists() else "python3"
    return str(python_path)


def cmd_install(args: argparse.Namespace) -> None:
    """Installera dependencies i per-agent virtualenv."""
    name = getattr(args, "name", None)
    if name:
        _validate_name(name)
        targets = [AGENTS_DIR / name]
        if not targets[0].exists():
            print(f"❌ Agent '{name}' finns inte: {targets[0]}")
            sys.exit(1)
    else:
        targets = _list_agents()
        if not targets:
            print("🤷 Inga agenter att installera.")
            return

    ok = True
    for agent_dir in targets:
        reqs = agent_dir / "requirements.txt"
        if not reqs.exists():
            continue
        name = agent_dir.name
        print(f"📦 Installerar {name}...")
        python = _ensure_agent_venv(agent_dir)
        r = subprocess.run(
            [python, "-m", "pip", "install", "-r", str(reqs), "-q"],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode == 0:
            print(f"   ✅ {name} OK")
        else:
            print(f"   ❌ {name}: {r.stderr[:200]}")
            ok = False

    if ok:
        print("✅ Alla dependencies installerade.")
    else:
        sys.exit(1)


def cmd_remove(args: argparse.Namespace) -> None:
    """Ta bort en agent (mapp, loggar, config-override)."""
    name = _validate_name(args.name)
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        print(f"❌ Agent '{name}' finns inte: {agent_dir}")
        sys.exit(1)

    import shutil
    shutil.rmtree(agent_dir)
    print(f"🗑️  Agentmapp borttagen: {agent_dir}")

    # Städa loggar
    log_file = OVERLORD_DIR / "logs" / f"{name}.jsonl"
    if log_file.exists():
        log_file.unlink()
        print(f"   Loggar borttagna: {log_file}")

    # Städa config-override
    over_cfg = OVERLORD_DIR / "config.yaml"
    if over_cfg.exists():
        try:
            cfg = yaml.safe_load(over_cfg.read_text()) or {}
            overrides = cfg.get("overrides", {})
            if name in overrides:
                del overrides[name]
                cfg["overrides"] = overrides
                over_cfg.write_text(yaml.dump(cfg, default_flow_style=False, allow_unicode=True))
                print(f"   Config-override borttagen från {over_cfg}")
        except Exception:
            pass

    print(f"✅ Agent '{name}' borttagen.")


def cmd_validate(args: argparse.Namespace) -> None:
    """Validera en agents konfiguration."""
    name = _validate_name(args.name)
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        print(f"❌ Agent '{name}' finns inte: {agent_dir}")
        sys.exit(1)

    ok = True

    # Validera agent.yaml
    cfg = _read_config(agent_dir)
    if cfg is None:
        ok = False

    # Validera cron-uttryck
    cron = cfg.get("cron") if cfg else None
    if cron:
        try:
            import re
            # Enkel cron-validering: 5 eller 6 fält med siffror/komma/stjärna/snabel
            fields = cron.strip().split()
            if len(fields) not in (5, 6):
                print(f"❌ Ogiltigt cron-uttryck '{cron}': förväntar 5-6 fält, fick {len(fields)}")
                ok = False
            else:
                for f in fields:
                    if not re.match(r'^[\d\*,/\-]+$', f) and f != '*':
                        print(f"⚠️  Cron-fält '{f}' ser ovanligt ut")
        except Exception as e:
            print(f"⚠️  Kunde inte validera cron: {e}")

    # Validera skills
    for skill in cfg.get("skills", []):
        module_path = agent_dir / "skills" / f"{skill['module'].split('.')[-1]}.py"
        if not module_path.exists():
            print(f"❌ Skill '{skill['name']}' ({skill['module']}): modul saknas: {module_path}")
            ok = False

        # Syntax-koll på skill-modulen
        if module_path.exists():
            try:
                compile(module_path.read_text(), str(module_path), "exec")
            except SyntaxError as e:
                print(f"❌ Skill '{skill['name']}': syntaxfel: {e}")
                ok = False

    # Validera main.py
    main_py = agent_dir / "main.py"
    if not main_py.exists():
        print(f"❌ main.py saknas")
        ok = False
    else:
        try:
            compile(main_py.read_text(), str(main_py), "exec")
        except SyntaxError as e:
            print(f"❌ main.py: syntaxfel: {e}")
            ok = False

    # Validera model config
    model = cfg.get("model", {})
    if not model.get("name"):
        print(f"❌ model.name saknas i agent.yaml")
        ok = False
    if not model.get("api_base"):
        print(f"⚠️  model.api_base saknas — använder default")

    if ok:
        print(f"✅ Agent '{name}' är OK ({len(cfg.get('skills', []))} skills, cron: {cron or '—'})")
    else:
        sys.exit(1)


def cmd_env(args: argparse.Namespace) -> None:
    """Visa eller editera .env-fil."""
    env_path = AGENTS_DIR.parent / ".env"
    from agentkit.utils import read_env_file, write_env_file

    show = getattr(args, "show", False)
    key = getattr(args, "key", None)
    value = getattr(args, "value", None)

    if key and value:
        # Sätt env var
        env = read_env_file(AGENTS_DIR.parent)
        env[key] = value
        write_env_file(AGENTS_DIR.parent, env)
        print(f"✅ {key}={value}")
    elif key and value == "":
        # Ta bort env var
        env = read_env_file(AGENTS_DIR.parent)
        if key in env:
            del env[key]
            write_env_file(AGENTS_DIR.parent, env)
        print(f"🗑️  {key} borttagen")
    elif key:
        # Visa specifik
        env = read_env_file(AGENTS_DIR.parent)
        if key in env:
            from agentkit.utils import mask_secrets
            print(mask_secrets(f"{key}={env[key]}"))
        else:
            print(f"❌ {key} finns inte i .env")
    elif show or not key:
        # Visa alla
        env = read_env_file(AGENTS_DIR.parent)
        if not env:
            print("📭 .env är tom eller finns inte.")
            return
        from agentkit.utils import mask_secrets
        for k, v in sorted(env.items()):
            print(mask_secrets(f"{k}={v}"))


def cmd_scaffold(args: argparse.Namespace) -> None:
    """Create a new agent scaffold."""
    args.name = _validate_name(args.name)
    agent_dir = AGENTS_DIR / args.name

    if agent_dir.exists():
        print(f"❌ Agent '{args.name}' finns redan: {agent_dir}")
        sys.exit(1)

    agent_dir.mkdir(parents=False)
    (agent_dir / "skills").mkdir()
    (agent_dir / "skills" / "__init__.py").touch()
    (agent_dir / "skills" / "example_skill.py").write_text(
        '"""Exempelskills — ersätt med faktisk implementation."""\n\n\ndef run(**kwargs) -> dict:\n    """Kör skillets logik. Motta parametrar från agentens pipeline."""\n    return {"status": "ok", "result": "placeholder"}\n'
    )

    use_react = getattr(args, "react", False)

    (agent_dir / "agent.yaml").write_text(
        AGENT_YAML_TEMPLATE.format(name=args.name)
    )
    (agent_dir / "main.py").write_text(
        (REACT_MAIN_PY_TEMPLATE if use_react else MAIN_PY_TEMPLATE).format(name=args.name)
    )
    (agent_dir / "requirements.txt").write_text(REQUIREMENTS_TEMPLATE)

    print(f"✅ Agent '{args.name}' skapad: {agent_dir}")
    print(f"   {agent_dir}/agent.yaml")
    print(f"   {agent_dir}/main.py")
    print(f"   {agent_dir}/skills/__init__.py")
    print(f"   {agent_dir}/requirements.txt")


def _resolve_agent_dir(name: str) -> Path:
    """Hitta agentkatalog — först AGENTS_DIR/name, sen cwd/name."""
    d = AGENTS_DIR / name
    if d.exists():
        return d
    d = Path.cwd() / name
    if d.exists() and (d / "agent.yaml").exists():
        return d
    return AGENTS_DIR / name  # fallerar med normalt felmeddelande


def cmd_run(args: argparse.Namespace) -> None:
    """Run an agent via subprocess with venv Python."""
    agent_dir = _resolve_agent_dir(args.name)

    if not agent_dir.exists():
        print(f"❌ Agent '{args.name}' finns inte: {agent_dir}")
        sys.exit(1)

    # Läs och validera config
    cfg = _read_config(agent_dir)
    if cfg is None:
        sys.exit(1)

    # Kolla beroenden
    _check_deps(agent_dir)

    dry_run = getattr(args, "dry_run", False)

    # Timeout: CLI-flagga > agent.yaml > default 300
    timeout = getattr(args, "timeout", None)
    if timeout is None:
        timeout = cfg.get("timeout", 300)

    # Git hash för commit-spårning
    git_hash = _get_git_hash()

    # Bygg env med agent-config
    start = time.time()
    env = os.environ.copy()
    if "model" in cfg:
        env["AGENT_MODEL_NAME"] = cfg["model"].get("name", "")
        env["AGENT_MODEL_API_BASE"] = cfg["model"].get("api_base", "")
    if cfg.get("instructions"):
        env["AGENT_INSTRUCTIONS"] = cfg["instructions"]

    if dry_run:
        env["HARNESS_DRY_RUN"] = "true"
        side_effects = [
            s["name"] for s in cfg.get("skills", [])
            if s.get("side_effect")
        ]
        if side_effects:
            env["HARNESS_DRY_RUN_SKILLS"] = ",".join(side_effects)

    # Ladda headroom-context från tidigare körningar
    ctx = headroom_memory("list", agent=cfg["name"], limit=3, since="7d")
    if ctx.get("stdout"):
        env["AGENT_CONTEXT"] = ctx["stdout"]

    main_py = agent_dir / "main.py"
    if not main_py.exists():
        print(f"❌ Ingen main.py i {agent_dir}")
        sys.exit(1)

    # Använd per-agent venv om det finns, annars huvud-venv
    agent_venv = agent_dir / ".venv" / "bin" / "python3"
    python = str(agent_venv) if agent_venv.exists() else (str(VENV_PYTHON) if VENV_PYTHON.exists() else "python3")
    print(f"🚀 Kör agent '{cfg['name']}' med {python}...")

    try:
        result = subprocess.run(
            [python, str(main_py)], env=env,
            capture_output=True, text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        duration = time.time() - start
        log_entry = dict(
            agent=cfg["name"],
            ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            status="error", code=-1, duration_s=round(duration, 2),
            dry_run=dry_run, stdout="", result=None,
            error=f"timeout ({timeout}s)",
            version=git_hash,
            tokens=0,
        )
        _write_log_entry(log_entry)
        print(f"❌ Agent '{cfg['name']}' timeout efter {timeout}s")
        _alert_on_failure(cfg["name"], f"timeout ({timeout}s)", log_entry)
        sys.exit(1)
    duration = time.time() - start

    # Logga
    log_entry = dict(
        agent=cfg["name"],
        ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        status="ok" if result.returncode == 0 else "error",
        code=result.returncode, duration_s=round(duration, 2),
        dry_run=dry_run, stdout=result.stdout, result=None,
        error=result.stderr if result.returncode != 0 else None,
        version=git_hash,
        tokens=len(result.stdout) // 4 if result.stdout else 0,
    )

    # Kolla efter CHAIN_OUTPUT (från raw stdout — före rtk-kompression)
    chain_output = None
    if result.stdout:
        for line in result.stdout.splitlines():
            if line.startswith("CHAIN_OUTPUT:"):
                try:
                    chain_output = json.loads(line[len("CHAIN_OUTPUT:"):])
                except json.JSONDecodeError:
                    pass
        log_entry["result"] = chain_output

    _write_log_entry(log_entry)

    # Komprimera stdout med rtk för token-snål utskrift
    display_stdout = rtk_compress(result.stdout) if result.stdout else ""
    print(display_stdout)

    # Spara sammanfattning till headroom om körningen lyckades
    if result.returncode == 0 and result.stdout:
        summary = (chain_output and json.dumps(chain_output, ensure_ascii=False)[:200]) or result.stdout.strip()[:200]
        headroom_memory("save", agent=cfg["name"], summary=summary, tags=["run"])

    # Chain: om agent.yaml har chain-konfig och föregående steg gick bra
    chain_cfg = cfg.get("chain")
    no_chain = getattr(args, "no_chain", False)
    if not no_chain and result.returncode == 0 and chain_output and chain_cfg:
        next_agent = chain_cfg.get("next_agent")
        mapping = chain_cfg.get("mapping", {})
        if next_agent:
            next_dir = AGENTS_DIR / next_agent
            if next_dir.exists():
                for output_key, input_key in mapping.items():
                    if output_key in chain_output:
                        val = chain_output[output_key]
                        if isinstance(val, str):
                            env[f"CHAIN_INPUT_{input_key}"] = val
                        else:
                            env[f"CHAIN_INPUT_{input_key}"] = json.dumps(val, ensure_ascii=False)

                env["CHAIN_FROM"] = cfg["name"]

                print(f"⛓️  Kedjar vidare till '{next_agent}'...")
                next_result = subprocess.run(
                    [python, str(next_dir / "main.py")], env=env,
                    capture_output=True, text=True,
                )

                next_duration = time.time() - start - duration
                next_log_entry = {
                    "agent": next_agent,
                    "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                    "status": "ok" if next_result.returncode == 0 else "error",
                    "code": next_result.returncode,
                    "duration_s": round(next_duration, 2),
                    "dry_run": dry_run,
                    "stdout": next_result.stdout,
                    "result": None,
                    "error": next_result.stderr if next_result.returncode != 0 else None,
                    "chained_from": cfg["name"],
                    "version": git_hash,
                }
                log_dir = OVERLORD_DIR / "logs"
                next_log_file = log_dir / f"{next_agent}.jsonl"
                with open(next_log_file, "a") as f:
                    f.write(json.dumps(next_log_entry, ensure_ascii=False) + "\n")

                print(rtk_compress(next_result.stdout or ""))
                if next_result.returncode != 0:
                    print(next_result.stderr)
                    sys.exit(next_result.returncode)
            else:
                print(f"⚠️  Chain: agent '{next_agent}' finns inte")

    if result.returncode != 0:
        print(result.stderr)
        _alert_on_failure(cfg["name"], result.stderr[:500] or f"exit code {result.returncode}", log_entry)
        sys.exit(result.returncode)


def cmd_cron_list(args: argparse.Namespace) -> None:
    """List all agents with cron schedules."""
    found = False
    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir() or agent_dir.name.startswith("."):
            continue
        cfg = _read_config(agent_dir)
        if cfg is None:
            continue
        name = cfg.get("name", agent_dir.name)
        cron = cfg.get("cron")
        if cron:
            print(f"⏰ {name:20s} cron: {cron}")
        else:
            print(f"💤 {name:20s} ingen cron")
        found = True
    if not found:
        print("🤷 Inga agenter hittades.")


def cmd_cron_run(args: argparse.Namespace) -> None:
    """Run a specific agent's cron job."""
    cmd_run(args)


def cmd_log(args: argparse.Namespace) -> None:
    """Visa loggar för en eller alla agenter."""
    log_dir = OVERLORD_DIR / "logs"
    if not log_dir.exists():
        print("📭 Inga loggar än.")
        return

    name = getattr(args, "name", None)
    tail = getattr(args, "tail", False)
    as_json = getattr(args, "json", False)
    n = getattr(args, "n", 5)
    since = getattr(args, "since", None)
    until = getattr(args, "until", None)
    level = getattr(args, "level", None)

    if name:
        log_file = log_dir / f"{name}.jsonl"
        if not log_file.exists():
            print(f"📭 Inga loggar för '{name}'.")
            return
        lines = log_file.read_text().splitlines()
        entries = []
        for l in lines:
            if l.strip():
                try:
                    entries.append(json.loads(l))
                except json.JSONDecodeError:
                    continue  # ponytail: hoppa över korrupta rader
        selected = entries[-n:] if n else entries

        # Filtrera på tid och status
        if since:
            selected = [e for e in selected if e.get("ts", "") >= since]
        if until:
            selected = [e for e in selected if e.get("ts", "") <= until + "T23:59:59"]
        if level:
            selected = [e for e in selected if e.get("status") == level]

        if as_json:
            for e in selected:
                print(json.dumps(e, ensure_ascii=False))
            return

        if tail:
            os.execvp("tail", ["tail", "-f", str(log_file)])

        for e in reversed(selected):
            icon = "✅" if e["status"] == "ok" else "❌"
            dry = " [DRY]" if e.get("dry_run") else ""
            print(f"{icon} {e['agent']:20s} {e['ts'][:19]}  {e['duration_s']:5.1f}s{dry}")
            if e.get("error"):
                print(f"   └─ {e['error'][:120]}")
    else:
        # Visa senaste per agent
        agent_statuses = {}
        for f in sorted(log_dir.glob("*.jsonl")):
            agent = f.stem
            file_lines = f.read_text().splitlines()
            if not file_lines:
                continue
            try:
                last = json.loads(file_lines[-1])
            except json.JSONDecodeError:
                continue
            agent_statuses[agent] = last

        if not agent_statuses:
            print("📭 Inga loggar.")
            return

        print(f"{'Agent':20s} {'Status':6s} {'Senast':20s} {'Tid':>6s}")
        print("-" * 55)
        for agent, e in sorted(agent_statuses.items()):
            icon = "✅" if e["status"] == "ok" else "❌"
            dry = " DRY" if e.get("dry_run") else ""
            print(f"{icon} {agent:18s} {e['status']:6s} {e['ts'][:19]} {e['duration_s']:5.1f}s{dry}")


def cmd_overlord_start(args: argparse.Namespace) -> None:
    """Starta overlord.py som bakgrundsprocess."""
    pid_path = OVERLORD_DIR / "overlord.pid"
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)
            print(f"⚠️  Overlord körs redan (PID {pid})")
            return
        except (ProcessLookupError, ValueError):
            pid_path.unlink(missing_ok=True)

    overlord_py = OVERLORD_DIR / "overlord.py"
    if not overlord_py.exists():
        print(f"❌ {overlord_py} finns inte. Skapa först.")
        return

    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else "python3"
    proc = subprocess.Popen(
        [python, str(overlord_py)],
        stdout=open(OVERLORD_DIR / "watchdog.log", "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    pid_path.write_text(str(proc.pid))
    print(f"✅ Overlord startad (PID {proc.pid})")


def cmd_overlord_stop(args: argparse.Namespace) -> None:
    """Stoppa overlord daemon."""
    pid_path = OVERLORD_DIR / "overlord.pid"
    if not pid_path.exists():
        print("⚠️  Overlord körs inte (ingen PID-fil)")
        return
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        pid_path.unlink()
        print(f"✅ Overlord stoppad (PID {pid})")
    except (ProcessLookupError, ValueError, OSError) as e:
        print(f"⚠️  Kunde inte stoppa: {e}")
        pid_path.unlink(missing_ok=True)


def cmd_overlord_status(args: argparse.Namespace) -> None:
    """Visa overlord-status."""
    pid_path = OVERLORD_DIR / "overlord.pid"
    if not pid_path.exists():
        print("💤 Overlord: stoppad")
        return
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, 0)
        import stat
        from datetime import datetime
        mtime = datetime.fromtimestamp(pid_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"✅ Overlord: körs (PID {pid}, startad {mtime})")
    except (ProcessLookupError, ValueError):
        print("💤 Overlord: PID-fil finns men processen är död (stale)")
        pid_path.unlink(missing_ok=True)


def cmd_tunnel(args: argparse.Namespace) -> None:
    """Öppna en publik tunnel till lokal port med bore, cloudflared eller SSH."""
    port = args.port
    host = args.host
    tunnel = None

    # Hantera token
    token_arg = getattr(args, "token", False)
    dashboard_token = None
    if token_arg:
        if token_arg is True:
            dashboard_token = secrets.token_urlsafe(32)
        else:
            dashboard_token = str(token_arg)
        from agentkit.utils import read_env_file, write_env_file
        env_path = AGENTS_DIR.parent / ".env"
        env = read_env_file(AGENTS_DIR.parent)
        env["DASHBOARD_TOKEN"] = dashboard_token
        write_env_file(AGENTS_DIR.parent, env)
        print(f"🔑 DASHBOARD_TOKEN satt i .env")

    # Fallback 1: bore (cross-platform, brew install bore-cli)
    bore_bin = shutil.which("bore")
    if bore_bin:
        cmd = [bore_bin, "local", str(port), "--to", "bore.pub"]
        if args.remote_port:
            cmd += ["--port", str(args.remote_port)]
        tunnel = cmd
        label = "bore"

    # Fallback 2: cloudflared (brew install cloudflared)
    if not tunnel:
        cf = shutil.which("cloudflared")
        if cf:
            tunnel = [cf, "tunnel", "--url", f"http://{host}:{port}"]
            label = "cloudflared"

    if not tunnel:
        print("⚠️  Ingen tunnel-klient hittad. Installera en:")
        print()
        print("  Mac (Homebrew):  brew install bore-cli")
        print("  Linux:           cargo install bore-cli")
        print("  Alla:            npm install -g cloudflared")
        print()
        print("  Eller SSH:  ssh -R 80:{}:{} nokey@localhost.run".format(host, port))
        sys.exit(1)

    print(f"🚇 Tunnel ({label}) → http://{host}:{port}")
    print("   Tryck Ctrl+C för att stänga\n")
    try:
        proc = subprocess.Popen(tunnel, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in iter(proc.stdout.readline, ""):
            line = line.rstrip()
            if "listening at" in line:
                url = line.split("listening at ")[-1]
                if dashboard_token:
                    print(f"\n   🌍  http://{url}?token={dashboard_token}\n")
                else:
                    print(f"\n   🌍  http://{url}\n")
            sys.stdout.write(f"   {line}\n")
            sys.stdout.flush()
    except KeyboardInterrupt:
        print("\n⏹  Stänger tunnel...")
        proc.terminate()
        proc.wait()


def cmd_overlord_logs(args: argparse.Namespace) -> None:
    """Visa watchdog.log."""
    log_path = OVERLORD_DIR / "watchdog.log"
    if not log_path.exists():
        print("📭 Inga watchdog-loggar än.")
        return
    tail = getattr(args, "tail", False)
    n = getattr(args, "n", 20)

    if tail:
        os.execvp("tail", ["tail", "-f", str(log_path)])

    lines = log_path.read_text().splitlines()
    for line in lines[-n:]:
        print(line)




# ── Setup ───────────────────────────────────────────────────────────────

def cmd_dashboard(args: argparse.Namespace) -> None:
    """Starta dashboard + tunnel i ett kommando."""
    from agentkit.utils import read_env_file as _rd, write_env_file as _wr

    # 1. Läs/generera token
    env = _rd(AGENTS_DIR.parent)
    token = env.get("DASHBOARD_TOKEN") or secrets.token_urlsafe(32)
    if "DASHBOARD_TOKEN" not in env:
        env["DASHBOARD_TOKEN"] = token
        _wr(AGENTS_DIR.parent, env)
    os.environ["DASHBOARD_TOKEN"] = token

    port = getattr(args, "port", 5050)

    # 2. Starta Flask
    flask_python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    flask_proc = subprocess.Popen(
        [flask_python, str(AGENTS_DIR / "dashboard" / "app.py")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    print(f"  📊 Dashboard startad (PID {flask_proc.pid})")

    # 3. Starta tunnel med logg för URL-detektion
    bore_bin = shutil.which("bore")
    tunnel_proc = None
    url = f"http://localhost:{port}?token={token}"
    if bore_bin:
        bore_log = AGENTS_DIR / ".overlord" / "bore.log"
        bore_log.parent.mkdir(parents=True, exist_ok=True)
        tunnel_proc = subprocess.Popen(
            [bore_bin, "local", str(port), "--to", "bore.pub"],
            stdout=open(bore_log, "w"), stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        print(f"  🚇 Tunnel startad (PID {tunnel_proc.pid})")
        # Vänta på bore-anslutning och fånga URL
        for _ in range(15):
            time.sleep(1)
            log = bore_log.read_text()
            if "listening at" in log:
                remote = log.split("listening at ")[-1].strip()
                url = f"http://{remote}?token={token}"
                break
        print()
    else:
        print("  ⚠️  Ingen tunnel — installera: brew install bore-cli")
        print()

    print(f"  🌍  {url}")
    print()
    print("  Tryck Ctrl+C för att stänga ner allt")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  ⏹  Stänger...")
        if tunnel_proc:
            tunnel_proc.terminate()
            tunnel_proc.wait(timeout=5)
        flask_proc.terminate()
        flask_proc.wait(timeout=5)


def cmd_setup(args: argparse.Namespace) -> None:
    """Full installation: venv, CLI-verktyg, .env, Python-paket."""
    import shutil

    print("🚀 HelmRig — setup\n")

    # 1. .env
    env_path = AGENTS_DIR.parent / ".env"
    env_example = AGENTS_DIR.parent / ".env.example"
    if not env_path.exists() and env_example.exists():
        import shutil as _shutil
        _shutil.copy(env_example, env_path)
        print("  ✅ .env skapad från .env.example — redigera med dina API-nycklar")
    elif env_path.exists():
        print("  ✅ .env finns redan")
    else:
        print("  ⚠️  .env saknas och ingen .env.example — skapa manuellt")

    # 1b. DASHBOARD_TOKEN
    from agentkit.utils import read_env_file as _rd, write_env_file as _wr
    _env = _rd(AGENTS_DIR.parent)
    if "DASHBOARD_TOKEN" not in _env:
        _env["DASHBOARD_TOKEN"] = secrets.token_urlsafe(32)
        _wr(AGENTS_DIR.parent, _env)
        print(f"  🔑 DASHBOARD_TOKEN genererad")
    else:
        print(f"  ✅ DASHBOARD_TOKEN finns redan")

    # 2. Projekt-venv
    venv_python = AGENTS_DIR.parent / ".venv" / "bin" / "python3"
    if not venv_python.exists():
        print("  🔧 Skapar projekt-venv...")
        r = subprocess.run(
            [sys.executable, "-m", "venv", str(AGENTS_DIR.parent / ".venv")],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode == 0:
            print("  ✅ Projekt-venv skapat")
        else:
            print(f"  ❌ Kunde inte skapa venv: {r.stderr[:200]}")
    else:
        print("  ✅ Projekt-venv finns redan")

    # 3. Installera Python-paket (med --only-binary för att undvika compilation)
    pip = str(venv_python) + " -m pip"
    print("  📦 Installerar Python-paket (bas)...")
    r = subprocess.run(
        f"{pip} install -q --only-binary :all: pyyaml langgraph langchain-core langchain-openai flask".split(),
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode == 0:
        print("  ✅ Baspaket installerade")
    else:
        # Fallback: försök utan --only-binary
        r2 = subprocess.run(
            f"{pip} install -q pyyaml langgraph langchain-core langchain-openai flask".split(),
            capture_output=True, text=True, timeout=120,
        )
        if r2.returncode == 0:
            print("  ✅ Baspaket installerade")
        else:
            print(f"  ⚠️  Vissa paket misslyckades: {r2.stderr[:200]}")

    # 4. rtk
    rtk_path = Path(os.path.expanduser("~/.local/bin/rtk"))
    if not rtk_path.exists():
        print("  📥 Installerar rtk (token-kompression)...")
        _install_cli("rtk", "https://rtk.dev/install")
    else:
        print("  ✅ rtk finns redan")

    # 5. headroom
    headroom_path = Path(os.path.expanduser("~/.local/bin/headroom"))
    if not headroom_path.exists():
        print("  📥 Installerar headroom (context-minne)...")
        _install_cli("headroom", "https://headroom.dev/install")
    else:
        print("  ✅ headroom finns redan")

    # 6. composio
    composio_path = shutil.which("composio")
    if not composio_path:
        print("  📥 Installerar composio (app-integrationer)...")
        _install_cli("composio", "https://composio.dev/install")
    else:
        print("  ✅ composio finns redan")

    # 7b. bore (tunnel)
    if not shutil.which("bore"):
        _brew = shutil.which("brew")
        _cargo = shutil.which("cargo")
        if _brew:
            print("  🚇 Installerar bore (tunnel)...")
            subprocess.run([_brew, "install", "bore-cli"], capture_output=True, text=True, timeout=120)
            if shutil.which("bore"):
                print("  ✅ bore installerat")
            else:
                print("  ⚠️  bore kunde inte installeras — försök: brew install bore-cli")
        elif _cargo:
            print("  🚇 Installerar bore (tunnel) via cargo...")
            subprocess.run([_cargo, "install", "bore-cli"], capture_output=True, text=True, timeout=120)
            if shutil.which("bore"):
                print("  ✅ bore installerat")
            else:
                print("  ⚠️  bore kunde inte installeras — försök: cargo install bore-cli")
        else:
            print("  ⚠️  bore saknas — installera med: brew install bore-cli")
    else:
        print("  ✅ bore finns redan")

    # 7c. composio-core Python-paket
    try:
        import composio  # noqa: F401
        print("  ✅ composio-core (Python SDK) finns redan")
    except ImportError:
        print("  📦 Installerar composio-core (Python SDK)...")
        r = subprocess.run(
            f"{pip} install -q --only-binary :all: composio-core".split(),
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode == 0:
            print("  ✅ composio-core installerat")
        else:
            print(f"  ⚠️  composio-core misslyckades, försök manuellt:")
            print(f"       {pip} install composio-core")

    # 7d. Auto-start för Overlord (systemd/Linux eller launchd/macOS)
    root_dir = str(AGENTS_DIR.parent.resolve())
    if sys.platform == "linux":
        service_src = OVERLORD_DIR / "overlord.service"
        if service_src.exists():
            systemd_dir = Path(os.path.expanduser("~/.config/systemd/user"))
            systemd_dir.mkdir(parents=True, exist_ok=True)
            content = service_src.read_text().replace("__ROOT_DIR__", root_dir)
            (systemd_dir / "overlord.service").write_text(content)
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, timeout=30)
            subprocess.run(["systemctl", "--user", "enable", "overlord.service"], capture_output=True, timeout=30)
            print("  ✅ Overlord systemd-service installerad — startar automatiskt vid boot")
        else:
            print(f"  ⚠️  {service_src} saknas — overlord startar inte automatiskt")
    elif sys.platform == "darwin":
        plist_src = OVERLORD_DIR / "overlord.plist"
        if plist_src.exists():
            launchd_dir = Path(os.path.expanduser("~/Library/LaunchAgents"))
            launchd_dir.mkdir(parents=True, exist_ok=True)
            content = plist_src.read_text().replace("__ROOT_DIR__", root_dir)
            plist_dst = launchd_dir / "com.helmrig.overlord.plist"
            plist_dst.write_text(content)
            subprocess.run(["launchctl", "load", str(plist_dst)], capture_output=True, timeout=30)
            print("  ✅ Overlord launchd-plist installerad — startar automatiskt vid inloggning")
        else:
            print(f"  ⚠️  {plist_src} saknas — overlord startar inte automatiskt")
    else:
        print(f"  ⚠️  Auto-start stöds inte på {sys.platform} — starta overlord manuellt")

    # Summary
    print()
    print("  ─────────────────────────────────────────────")
    print("  ✅ Setup klart!")
    print()
    print("  📋 Nästa steg:")
    print("     1. Redigera .env med dina API-nycklar")
    print("     2. Logga in på composio och koppla appar:")
    print("        composio login              # OAuth via browser")
    print("        # Första gången du kör en composio-skill ansluts automatiskt")
    print("        # eller: composio search 'send email' för att hitta fler appar")
    print("     3. Skapa din första agent:")
    print("        harness scaffold min-agent --react")
    print("        harness install min-agent")
    print("     4. Kör:")
    print("        harness run min-agent")
    print("     5. Starta dashboard:")
    print("        harness dashboard")


def _install_cli(name: str, url: str):
    """Ladda ner och installera ett CLI-verktyg via officiella installern."""
    import urllib.request
    import shutil as _shutil

    try:
        # Använd curl -fsSL för att efterlikna manuell installation
        r = subprocess.run(
            ["bash", "-c", f"curl -fsSL {url} | bash"],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode == 0:
            print(f"  ✅ {name} installerad")
        else:
            print(f"  ⚠️  {name} misslyckades: {r.stderr[:200]}")
            print(f"     Installera manuellt: curl -fsSL {url} | bash")
    except Exception as e:
        print(f"  ⚠️  {name} misslyckades: {e}")
        print(f"     Installera manuellt: curl -fsSL {url} | bash")


# ── Doctor ──────────────────────────────────────────────────────────────

def cmd_doctor(args: argparse.Namespace) -> None:
    """Kontrollera att alla beroenden finns installerade."""
    import shutil

    print("🔍 HelmRig — diagnos\n")

    checks = [
        ("Python 3.12+", sys.version_info >= (3, 12)),
        (".env finns", (AGENTS_DIR.parent / ".env").exists()),
        ("rtk (token-kompression)", Path(os.path.expanduser("~/.local/bin/rtk")).exists()),
        ("headroom (context-minne)", Path(os.path.expanduser("~/.local/bin/headroom")).exists()),
        ("composio CLI (app-integrationer)", shutil.which("composio") is not None),
    ]

    for label, ok in checks:
        print(f"  {'✅' if ok else '❌'} {label}")

    # Kolla LangChain-paket
    print()
    print("  📦 Python-paket:")
    for pkg in ["langchain_openai", "langchain_anthropic", "langchain_google_genai",
                "langchain_ollama", "composio", "yaml", "flask", "langgraph"]:
        try:
            importlib.import_module(pkg)
            print(f"    ✅ {pkg}")
        except ImportError:
            print(f"    ❌ {pkg} — installera med: pip install {pkg.replace('_', '-')}")

    # Kolla composio connections
    print()
    print("  🔌 Composio connections:")
    try:
        r = subprocess.run(["composio", "list"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                if line.strip():
                    print(f"    {line.strip()}")
        else:
            print("    composio inte tillgängligt")
    except FileNotFoundError:
        print("    composio CLI inte installerat")

    # Kolla valfria agentkit-moduler
    print()
    print("  🔧 Agentkit extra-moduler:")
    _opt_modules = {
        "crawler": ("crawl4ai", "Webbcrawler (Crawl4AI)"),
        "memory": ("chromadb", "Vector store (Chroma)"),
        "mcp": ("mcp", "MCP-klient"),
        "tracer": ("langfuse", "Langfuse tracing"),
        "file_reader": ("pymupdf", "PDF-läsning (PyMuPDF)"),
    }
    for mod_name, (pkg, label) in _opt_modules.items():
        try:
            importlib.import_module(pkg)
            print(f"    ✅ {mod_name} — {label}")
        except ImportError:
            print(f"    ❌ {mod_name} — {label}")
            print(f"       pip install -e \"agents/[{mod_name}]\"")

    print()
    print("  💡 Installera saknade verktyg:")
    print("    rtk:      curl -fsSL https://rtk.dev/install | bash")
    print("    headroom: curl -fsSL https://headroom.dev/install | bash")
    print("    composio: curl -fsSL https://composio.dev/install | bash")
    print("    agent:    harness install <namn>")


# ── CLI ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="harness",
        description="HelmRig Harness — scaffold, run, schedule",
    )
    sub = parser.add_subparsers(dest="command")

    # scaffold
    scaf = sub.add_parser("scaffold", help="Skapa en ny agent")
    scaf.add_argument("name", help="Agentnamn (mappnamn)")
    scaf.add_argument("--react", action="store_true", help="ReAct-loop (LLM väljer tools)")

    # list
    sub.add_parser("list", help="Lista alla agenter med status")
    sub.add_parser("ls", help="Lista alla agenter (alias för list)")

    # install
    install_parser = sub.add_parser("install", help="Installera dependencies")
    install_parser.add_argument("name", nargs="?", help="Agentnamn (utelämna för alla)")

    # remove (remove/rm delar parser)
    remove_parser = sub.add_parser("remove", help="Ta bort en agent")
    remove_parser.add_argument("name", help="Agentnamn")
    rm_parser = sub.add_parser("rm", help="Ta bort en agent (alias för remove)")
    rm_parser.add_argument("name", help="Agentnamn")

    # setup
    sub.add_parser("setup", help="Full installation: venv + CLI + Python-paket")

    # doctor
    sub.add_parser("doctor", help="Diagnos: kontrollera beroenden")

    # validate
    validate_parser = sub.add_parser("validate", help="Validera agentkonfiguration")
    validate_parser.add_argument("name", help="Agentnamn")

    # run
    run_parser = sub.add_parser("run", help="Kör en agent")
    run_parser.add_argument("name", help="Agentnamn")
    run_parser.add_argument("--dry-run", action="store_true", help="Kör utan side-effects")
    run_parser.add_argument("--no-chain", action="store_true", help="Hoppa över kedja")
    run_parser.add_argument("--timeout", type=int, default=None, help="Timeout i sekunder (default: 300)")

    # env
    env_parser = sub.add_parser("env", help="Visa/editera miljövariabler")
    env_parser.add_argument("key", nargs="?", help="Variabelnamn")
    env_parser.add_argument("value", nargs="?", help="Nytt värde (utelämna för att visa)")
    env_parser.add_argument("--show", action="store_true", help="Visa alla variabler")

    # cron
    cron_parser = sub.add_parser("cron", help="Cron-kommandon")
    cron_sub = cron_parser.add_subparsers(dest="cron_command")

    cron_list = cron_sub.add_parser("list", help="Lista cron-scheman")
    cron_run_p = cron_sub.add_parser("run", help="Kör en cron-job")
    cron_run_p.add_argument("name", help="Agentnamn")

    # log
    log_parser = sub.add_parser("log", help="Visa loggar")
    log_parser.add_argument("name", nargs="?", help="Agentnamn")
    log_parser.add_argument("-n", type=int, default=5, help="Antal rader")
    log_parser.add_argument("--tail", action="store_true", help="Följ live")
    log_parser.add_argument("--json", action="store_true", help="Rå JSON")
    log_parser.add_argument("--since", help="Tidigaste tid (ISO: 2026-07-20 eller 2026-07-20T12:00)")
    log_parser.add_argument("--until", help="Senaste tid (ISO)")
    log_parser.add_argument("--level", choices=["ok", "error", "never"], help="Filtrera på status")

    # dashboard
    dash_parser = sub.add_parser("dashboard", help="Starta dashboard + tunnel i ett")
    dash_parser.add_argument("port", type=int, nargs="?", default=5050, help="Port (default: 5050)")

    # tunnel
    tunnel_parser = sub.add_parser("tunnel", help="Öppna publik tunnel till lokal port")
    tunnel_parser.add_argument("port", type=int, nargs="?", default=5050, help="Lokal port (default: 5050)")
    tunnel_parser.add_argument("--host", default="localhost", help="Lokal host (default: localhost)")
    tunnel_parser.add_argument("--remote-port", type=int, default=0, help="Önskad remote port (bore)")
    tunnel_parser.add_argument("--token", metavar="TOKEN", nargs="?", const=True, default=False,
                               help="Inkludera auth-token i URL:en. Utan värde genereras ett nytt.")

    # overlord
    over_parser = sub.add_parser("overlord", help="Styr overlord daemon")
    over_sub = over_parser.add_subparsers(dest="overlord_command")
    over_sub.add_parser("start", help="Starta overlord")
    over_sub.add_parser("stop", help="Stoppa overlord")
    over_sub.add_parser("status", help="Visa status")
    over_logs = over_sub.add_parser("logs", help="Visa watchdog-loggar")
    over_logs.add_argument("-n", type=int, default=20, help="Antal rader")
    over_logs.add_argument("--tail", action="store_true", help="Följ live")

    args = parser.parse_args()

    if args.command in ("list", "ls"):
        cmd_list(args)
    elif args.command == "scaffold":
        cmd_scaffold(args)
    elif args.command == "install":
        cmd_install(args)
    elif args.command in ("remove", "rm"):
        cmd_remove(args)
    elif args.command == "setup":
        cmd_setup(args)
    elif args.command == "doctor":
        cmd_doctor(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "env":
        cmd_env(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "log":
        cmd_log(args)
    elif args.command == "cron":
        if args.cron_command == "list":
            cmd_cron_list(args)
        elif args.cron_command == "run":
            cmd_cron_run(args)
        else:
            cron_parser.print_help()
    elif args.command == "dashboard":
        cmd_dashboard(args)
    elif args.command == "tunnel":
        cmd_tunnel(args)
    elif args.command == "overlord":
        if args.overlord_command == "start":
            cmd_overlord_start(args)
        elif args.overlord_command == "stop":
            cmd_overlord_stop(args)
        elif args.overlord_command == "status":
            cmd_overlord_status(args)
        elif args.overlord_command == "logs":
            cmd_overlord_logs(args)
        else:
            over_parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
