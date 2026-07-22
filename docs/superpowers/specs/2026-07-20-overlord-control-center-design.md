# Overlord Control Center — Design

**Datum:** 2026-07-20
**Status:** Specifikation (godkänd av användare)

## Översikt

Bygg ut `.overlord/` från ett tomt loggarkiv till en riktig kontrollcentral: central config, watchdog-daemon, hälsoövervakning, och jobbkö.

**Arkitektur:** Harness + `.overlord/overlord.py` daemon. Agenterna är omedvetna om overlord — all config merge sker i harness innan agenten startas.

## Filer

```
.overlord/
├── config.yaml          # NY — central config (defaults + overrides)
├── overlord.py          # NY — daemon (watchdog + health + queue-consumer)
├── overlord.pid         # NY — PID-fil (skapas av overlord start)
├── watchdog.log         # NY — daemon-logg
├── queue/               # NY — jobbkö
│   ├── lock             # PID-fil: en agent körs
│   ├── stock-watcher-20260720T120000.json
│   └── svt-sarcastic-20260720T120100.json
└── logs/                # befintlig — JSONL per agent
    ├── stock-watcher.jsonl
    └── svt-sarcastic.jsonl
```

---

## 1. Central config (`config.yaml`)

### Struktur
```yaml
defaults:
  model:
    provider: deepseek
    name: deepseek-chat
    api_base: https://api.deepseek.com/v1

overrides:
  <agent-dir>:
    <key>: <value>

watchdog:
  enabled: true
  interval_s: 60
  max_restarts: 3

health:
  notify_on_missed_cron: true

queue:
  max_concurrent: 1
```

### Merge-regler
- `defaults` → appliceras på alla agenter som inte har värdet satt i sin agent.yaml
- `overrides.<agent>` → slår agentens egna värden (override, inte merge för skalärer)
- `watchdog`, `health`, `queue` → läses av harness och overlord.py
- Listor (tickers etc): override ersätter hela listan

### Implementation
Ny funktion i `harness.py`:
```python
def _load_overlord_config() -> dict:
    """Läs och returnera .overlord/config.yaml. Tom dict om ingen config finns."""
```

Anropas av `_read_config()` så att alla merged configvärden hamnar i env.

---

## 2. Watchdog + Health (overlord.py)

`harness overlord start|stop|status|logs` styr en bakgrundsprocess.

### Daemon-loop (`overlord.py`)
```python
while True:
    for agent in alla_agentkataloger:
        if watchdog_check(agent):     # har agenten crashat?
            restart_agent(agent)       # subprocess.run(["python3", "main.py"])
        if health_check(agent):        # missad cron? syntaxfel?
            log_warning(agent, reason) # logga till watchdog.log
    
    # Plocka nästa jobb från kön
    process_queue()
    
    time.sleep(interval)  # default 60s
```

### watchdog_check
- Läs senaste log-raden från `.overlord/logs/<agent>.jsonl`
- Om `status: error` och antal restarts < max_restarts → starta om
- Räkna restarts per timme (dict i minnet)

### health_check
- **Cron-koll:** Har agent.yaml cron? Kolla om senaste körningen är inom cron-fönstret + 10min
- **Syntax-koll:** `compile(open('main.py').read(), 'main.py', 'exec')` — logga error om den failar

### restart_agent
- `subprocess.run([python, str(main_py)])` — samma som harness run
- Logga omstart till watchdog.log

### Notifikation
Just nu: loggning till `watchdog.log`. Struktur:
```
[2026-07-20T14:05:00] RESTART stock-watcher — exit code 1, restart 1/3
[2026-07-20T14:05:00] WARN svt-sarcastic — cron 12:00 missad (senaste körning 2026-07-19)
```

### Loggformat
`watchdog.log` — plain text, en rad per händelse.

---

## 3. Harness CLI — nya subcommands

```python
# run — kolla jobbkö först
def cmd_run(args):
    if queue_active() and queue.max_concurrent <= active_count:
        queue_job(agent)
        print("⏳ Agenten är i kön. Väntar på ledig plats.")
        return
    # ... befintlig run-logik ...

# overlord
def cmd_overlord_start():
    """Starta overlord.py som bakgrundsprocess."""
    proc = subprocess.Popen([python, overlord_py], ...)
    proc.pid → .overlord/overlord.pid

def cmd_overlord_stop():
    """Döda overlord.py via PID-fil."""
    pid = read(.overlord/overlord.pid)
    os.kill(pid, SIGTERM)

def cmd_overlord_status():
    """Visa status + senaste watchdog.log-rader."""

def cmd_overlord_logs():
    """Tail watchdog.log."""

# queue
def cmd_queue_list():
    """Lista filer i queue/-katalogen."""
def cmd_queue_flush():
    """Rensa queue/-katalogen."""
```

### Subparser-struktur
```
harness overlord start|stop|status|logs
harness queue list|flush
```

---

## 4. Jobbkö

### Mekanik
- `harness run <agent>` → om en annan agent redan körs (queue/lock existerar och PID levande) → skapa `.overlord/queue/<agent>-<ts>.json`
- Kön konsumeras av overlord.py (process_queue i loopen)
- `queue/lock` är en PID-fil: processen som kör en agent skriver sin PID. Om PID:n inte lever → stale-lock, rensa.
- `queue.max_concurrent` från config.yaml

### Jobb-fil
`.overlord/queue/<agent>-<ts>.json`:
```json
{"agent": "stock-watcher", "ts": "2026-07-20T12:00:00", "dry_run": false}
```

---

## Ordning

1. config.yaml + `_load_overlord_config()` i harness
2. `harness overlord` subcommands (start/stop/status/logs)
3. overlord.py — watchdog + health loop
4. Jobbkö — lock + queue-filer + konsumtion i overlord.py
5. `harness queue` subcommands (list/flush)
