# AGENTS.md — HashScope

This repo contains **HashScope**, a Stratum MITM / proxy for observing miner↔pool traffic.
Iteration 1 is transparent relaying + capture + UI.
Iteration 2 adds a **distributed agent fleet** that receives “share events” via **Nostr relay subscriptions** (push), and can report telemetry back via the same protocol.

> Assumption: You have authorization to load test **your own pool**.

---

## High-level architecture

### Components
1. **MITM Proxy (local, Python, Docker)**
   - Accepts inbound miner connections
   - Connects upstream to pool
   - Relays traffic transparently
   - Captures messages (raw + decoded Stratum JSON-RPC)
   - **Iteration 2:** publishes “share events” to Nostr

2. **Nostr Relay (cloud, reachable)**
   - Acts as rendezvous for:
     - MITM proxy publishing share events
     - Agents subscribing to receive share events (no polling)
     - Agents publishing telemetry back
     - Orchestrator/UI subscribing to telemetry

3. **Agents (distributed, Python, Docker)**
   - Run on servers worldwide
   - Each agent:
     - Connects to the target pool directly (auth + get work like a normal miner)
     - Maintains an active subscription to Nostr relay for share events
     - When a share event arrives, performs the configured pool submit action
     - Publishes telemetry events back to relay

4. **Web UI (modern UI; prefer React + shadcn/ui)**
   - Iteration 1: message stream visualization from local API
   - Iteration 2: show agent status + telemetry live (via local API subscribing to Nostr)
   - UI does **not** need to talk to Nostr directly; backend can bridge.

### Data flow (Iteration 2)
- Main miner → MITM → pool: real share submission.
- MITM captures miner’s `mining.submit` (and related context if needed).
- MITM publishes a **ShareEvent** to Nostr relay.
- Agents maintain a WebSocket subscription to relay; they receive ShareEvent immediately.
- Agents submit (synthetically) to pool and record responses.
- Agents publish **TelemetryEvent** back to relay.
- Orchestrator (MITM backend) subscribes to TelemetryEvent and exposes it to UI via WebSocket.

---

## Iteration 2 goals

1. **No polling.** Agents must use Nostr WebSocket subscriptions (REQ) to receive events.
2. **Fleet operation.** Many agents can run concurrently across regions.
3. **Simple event protocol.** One shared protocol for:
   - MITM → agents (ShareEvent)
   - agents → orchestrator/UI (TelemetryEvent)
4. **Resilience.** Agents handle disconnect/reconnect and catch up without missing events.
5. **Safety / separation.**
   - MITM stays transparent by default.
   - “Fan-out” is additive: publishing ShareEvent must not block relaying.

---

## Nostr protocol usage

### Keys
- MITM has a long-lived Nostr keypair (`MITM_NOSTR_SK`).
- Each agent has its own keypair (`AGENT_NOSTR_SK`) or one shared test keypair (allowed, but per-agent is preferred).
- Events must be signed.

### Relay connections
- Use one primary relay URL (self-host preferred).
- Optional: secondary relay for redundancy.

### Subscriptions (push, not polling)
Agents open a persistent WebSocket connection to relay and send a REQ subscription:
- Filter by tags for `hashscope` + `run_id` + `type=share`.
- Keep subscription open.
- On reconnect, use `since` timestamp and/or last `seq` for catch-up.

### Event kinds
Use custom kinds to keep filtering simple.
- `KIND_SHARE_EVENT` (e.g. 30078) — MITM publishes
- `KIND_TELEMETRY_EVENT` (e.g. 30079) — agents publish

(Exact kind numbers are implementation choice; keep them in one constants module.)

### Tagging convention
All HashScope Nostr events MUST include:
- `["t", "hashscope"]`
- `["run", "<RUN_ID>"]`
- `["type", "share"]` OR `["type", "telemetry"]`

Optional tags:
- `["pool", "<POOL_ID_OR_HOST>"]`
- `["agent", "<AGENT_ID>"]` for telemetry
- `["schema", "hashscope.v1"]`

### Payload format
Event `content` is JSON string.

#### ShareEvent content (MITM → agents)
Minimum fields:
- `schema`: `"hashscope.v1"`
- `run_id`: string
- `event_id`: uuid
- `seq`: monotonically increasing integer (per run)
- `ts`: ISO-8601 UTC timestamp
- `pool`: `{ "host": "...", "port": 3333 }` (informational)
- `stratum`: `{ "method": "mining.submit", "id": <id>, "params": [...] }`
- `context`: optional decoded data useful for debug (worker name, extranonce sizes, etc.)
- `raw`: optional base64 (if needed); do not require raw for MVP

Notes:
- ShareEvent is a *notification*, not a guarantee.
- If share params need modification per agent session, agents must do it (future work). For now, they can submit as-is if that’s your intent.

#### TelemetryEvent content (agents → orchestrator)
Minimum fields:
- `schema`: `"hashscope.v1"`
- `run_id`: string
- `agent_id`: stable id (hostname/uuid)
- `ts`: ISO-8601 UTC timestamp
- `pool_target`: `{ "host": "...", "port": ... }`
- `conn_state`: `"connected" | "reconnecting" | "error"`
- `stats`:
  - `share_events_received_total`
  - `submits_attempted_total`
  - `submits_accepted_total`
  - `submits_rejected_total`
  - `last_submit_latency_ms` (optional)
- `errors`: list of recent error strings (bounded)

---

## Agent behavior (Iteration 2)

### Startup sequence
1. Load config (env vars + optional file).
2. Connect to pool and perform standard Stratum handshake/auth:
   - subscribe / authorize
   - request difficulty/work as needed by pool
3. Connect to Nostr relay WebSocket.
4. Send REQ subscription for ShareEvent events for this `RUN_ID`.
5. Begin main loop:
   - on ShareEvent: submit to pool; record result; increment counters
   - periodically publish TelemetryEvent (e.g., every 5s) and on notable errors

### Reconnect strategy
- If relay disconnects:
  - exponential backoff reconnect (cap at ~30s)
  - on reconnect, resubscribe with `since` = last_seen_ts - small overlap (e.g., 10s)
- If pool disconnects:
  - reconnect and redo handshake
  - keep relay subscription alive

### Backpressure / safety
- Submitting to pool should be bounded:
  - if events arrive faster than agent can submit (unlikely), drop or buffer with max queue.
- Telemetry is best-effort; never block submitting due to telemetry publishing.

---

## MITM behavior (Iteration 2)

### Publishing ShareEvent
- Detect Stratum share submissions from the real miner:
  - typically `mining.submit`
- Immediately publish ShareEvent to relay on a background task.
- Publishing must never block relaying; if relay is down, queue up to a limit and drop oldest.

### Subscribing to TelemetryEvent
- MITM backend connects to relay and maintains subscription for telemetry for `RUN_ID`.
- Expose aggregated agent status via local API for UI.

---

## Configuration (Iteration 2)

Common:
- `RUN_ID` (required; used to isolate streams)
- `NOSTR_RELAY_URL` (required)
- `NOSTR_RELAY_URL_SECONDARY` (optional)
- `NOSTR_KIND_SHARE` (default 30078)
- `NOSTR_KIND_TELEMETRY` (default 30079)
- `NOSTR_SK` (secret key) per component (MITM vs agent)

MITM:
- `POOL_HOST`, `POOL_PORT`
- `LISTEN_HOST`, `LISTEN_PORT`
- capture limits

Agent:
- `POOL_HOST`, `POOL_PORT` (target pool)
- `AGENT_ID` (default hostname)
- credentials:
  - `WORKER_NAME`
  - `WORKER_PASSWORD` (or token)
- telemetry interval:
  - `TELEMETRY_INTERVAL_SEC` (default 5)

---

## Repo structure (recommended)

- `backend/`
  - `hashscope/`
    - `proxy/` (TCP MITM)
    - `stratum/` (parsing/models)
    - `nostr/`
      - `client.py` (WS connect, publish, subscribe)
      - `schemas.py` (ShareEvent/TelemetryEvent models)
      - `constants.py` (kinds, tags)
    - `api/` (FastAPI REST + WS to UI)
- `agents/`
  - `hashscope_agent/`
    - `main.py` (agent entrypoint)
    - `pool_client.py` (stratum client)
    - `nostr_client.py`
- `frontend/`
  - React + shadcn/ui (optional for iteration 2 display)

Adapt if structure already exists.

---

## Commands (expected)

Backend:
- Tests: `pytest -q`
- Dev API: `uvicorn hashscope.api.app:app --reload --host 0.0.0.0 --port 8000`
- MITM proxy: `python -m hashscope.proxy.main`

Agent:
- Run: `python -m hashscope_agent.main`

Docker:
- Provide `docker-compose.yml` for:
  - `hashscope-mitm` (backend)
  - `hashscope-agent` (scalable via replicas; env-based config)
  - `frontend` (optional)
- Nostr relay is external (cloud), not part of compose.

---

## Acceptance criteria (Iteration 2)

1. MITM publishes a ShareEvent when the real miner submits a share.
2. Agents receive ShareEvent via subscription (no polling) and attempt a pool submit.
3. Agents publish telemetry events; MITM aggregates and exposes them via local API.
4. System remains stable if relay disconnects (reconnect + resubscribe).
5. Publishing to relay never blocks MITM traffic relaying.
6. Minimal tests:
   - schema validation for ShareEvent/TelemetryEvent
   - Nostr client reconnect logic (mock WS)
   - agent queue/backpressure behavior

---

## Notes / guardrails

- Keep Nostr event content minimal; avoid leaking secrets.
- Use `RUN_ID` everywhere to prevent cross-talk.
- If using public relays, assume rate limits; self-host is recommended for predictable behavior.