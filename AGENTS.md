# AGENTS.md — HashScope

This file tells coding agents how to work in this repo: goals, architecture, conventions, how to run/test, and what "done" means.

> **Assumption:** You have authorization to load test **your own pool**.

---

## Project summary

**HashScope** is a Bitcoin mining analysis platform consisting of:

1. **MITM Proxy** — sits between miners and a pool, transparently relaying Stratum traffic while capturing and decoding all messages for visualization and debugging.

2. **Distributed Agent Fleet** — a scalable network of agents that receive share events via Nostr relay subscriptions, submit them to target pools, and report telemetry back for analysis.

**Tech stack:**
- **Language:** Python (core proxy, API, agents)
- **Runtime:** Docker-first
- **UI:** Modern React with **shadcn/ui** components
- **Transport to UI:** WebSocket (live stream) + REST (query/history/config)
- **Agent coordination:** Nostr relay (push-based, no polling)

---

## High-level architecture

### Components

1. **MITM Proxy (local, Python, Docker)**
   - Accepts inbound miner connections (TCP)
   - Connects upstream to configured pool (TCP)
   - Relays traffic transparently (byte-for-byte)
   - Captures messages (raw + decoded Stratum JSON-RPC)
   - Publishes share events to Nostr relay
   - Subscribes to telemetry from agents
   - Exposes local API (REST + WebSocket) for UI

2. **Nostr Relay (cloud, reachable)**
   - Acts as rendezvous/pubsub for:
     - MITM proxy publishing share events
     - Agents subscribing to receive share events (no polling)
     - Agents publishing telemetry back
     - Orchestrator/UI subscribing to telemetry
   - Self-hosted preferred; external (cloud) deployment

3. **Distributed Agents (Python, Docker, multi-region)**
   - Run on servers worldwide
   - Each agent:
     - Connects to target pool directly (auth + get work like a normal miner)
     - Maintains active WebSocket subscription to Nostr relay for share events
     - On share event arrival, submits to pool and records result
     - Publishes telemetry events back to relay

4. **Web UI (React + shadcn/ui)**
   - Message stream visualization (live + history)
   - Session list and filtering
   - Agent fleet status + telemetry display
   - UI does **not** talk to Nostr directly; backend bridges

### Data flow

**Local traffic capture:**
- Real miner → MITM → pool: transparent relay
- MITM captures every message bidirectionally with timestamps
- MITM exposes via local API/WebSocket to UI

**Distributed fleet operation:**
- MITM captures miner's `mining.submit` (and context)
- MITM publishes **ShareEvent** to Nostr relay (background task, non-blocking)
- Agents maintain WebSocket subscription; receive ShareEvent immediately (push, no polling)
- Agents submit to pool and record responses
- Agents publish **TelemetryEvent** back to relay
- MITM backend subscribes to TelemetryEvent and exposes aggregated data via local API to UI

---

## Repo structure (recommended)

Agents should follow this layout unless it already exists:

```
├── backend/
│   ├── hashscope/
│   │   ├── proxy/           # TCP proxy, sessions, relay logic
│   │   ├── stratum/         # parsers/encoders, message models
│   │   ├── capture/         # event model, storage (in-memory ring buffers)
│   │   ├── nostr/           # Nostr client, schemas, constants
│   │   │   ├── client.py    # WebSocket connect, publish, subscribe
│   │   │   ├── schemas.py   # ShareEvent/TelemetryEvent models
│   │   │   └── constants.py # event kinds, tag conventions
│   │   ├── api/             # FastAPI app: REST + WebSocket to UI
│   │   └── config/          # Pydantic settings
│   └── tests/               # pytest
├── agents/
│   └── hashscope_agent/
│       ├── main.py          # agent entrypoint
│       ├── pool_client.py   # Stratum client
│       └── nostr_client.py  # Nostr subscription + telemetry
├── frontend/
│   ├── src/
│   │   ├── components/      # React + TypeScript (shadcn/ui)
│   │   └── ...
│   └── package.json
├── docker-compose.yml
└── Dockerfile (or per-service Dockerfiles)
```

**If the repo already has a different structure, adapt to it—do not reorganize unless asked.**

---

## Technology choices

### Backend
- **FastAPI** for REST + WebSocket endpoints
- **asyncio** for TCP proxying (use `asyncio.start_server` + stream readers/writers)
- **Structured logging** (JSON logs preferred)
- **Stratum parsing:**
  - Stratum v1 uses JSON-RPC over newline-delimited JSON
  - Parse line-delimited JSON as primary; always store raw bytes regardless
  - Best-effort decoding; never crash the proxy due to parsing errors

### Storage
- **Default:** In-memory ring buffer per session + global index
- **Optional:** SQLite (only if asked); keep abstraction so it can be swapped later

### Frontend
- **React + TypeScript** (Next.js or Vite)
- **shadcn/ui** components for tables, tabs, dialogs, badges, dropdowns
- Use WebSocket for live updates; paginate/history via REST

### Nostr integration
- Use a Python Nostr library (e.g., `nostr-sdk` or similar)
- Push-based subscriptions (WebSocket REQ), not polling
- Events must be signed with keypairs

---

## Configuration

Config should be possible via **environment variables** and a config file.

### MITM Proxy settings

**Network:**
- `LISTEN_HOST` (default `0.0.0.0`)
- `LISTEN_PORT` (default `3333`)
- `POOL_HOST` (required; never hardcode)
- `POOL_PORT` (default `3333` or pool-specific)
- `API_HOST` (default `0.0.0.0`)
- `API_PORT` (default `8000`)

**Capture:**
- `CAPTURE_MAX_MESSAGES` (default 50,000 total)
- `CAPTURE_MAX_PER_SESSION` (default 10,000)

**Nostr (MITM):**
- `RUN_ID` (required; used to isolate event streams)
- `NOSTR_RELAY_URL` (required)
- `NOSTR_RELAY_URL_SECONDARY` (optional)
- `NOSTR_KIND_SHARE` (default 30078)
- `NOSTR_KIND_TELEMETRY` (default 30079)
- `MITM_NOSTR_SK` (secret key for MITM)

### Agent settings

**Pool connection:**
- `POOL_HOST` (required; target pool to test)
- `POOL_PORT` (default `3333`)
- `WORKER_NAME` (required)
- `WORKER_PASSWORD` (or token)

**Nostr (Agent):**
- `RUN_ID` (must match MITM)
- `NOSTR_RELAY_URL` (same as MITM)
- `NOSTR_RELAY_URL_SECONDARY` (optional)
- `AGENT_NOSTR_SK` (secret key for agent; per-agent preferred)
- `AGENT_ID` (default: hostname)

**Telemetry:**
- `TELEMETRY_INTERVAL_SEC` (default 5)

---

## Message and event models

### Captured message model

Every captured Stratum message must include:

- `id`: monotonic or UUID
- `ts_recv`: timestamp when received by HashScope
- `ts_fwd`: timestamp when forwarded (if forwarded)
- `direction`: `miner_to_pool` | `pool_to_miner`
- `session_id`: stable identifier per TCP miner connection
- `peer`: miner IP:port (and/or pool IP:port)
- `raw`: base64 or escaped string representation of bytes
- `decoded`: structured dict when parse succeeds (e.g., JSON-RPC fields)
- `parse_error`: string if decode fails

### Nostr event models

#### ShareEvent (MITM → agents)

Published by MITM when a miner submits a share.

**Nostr event structure:**
- `kind`: `NOSTR_KIND_SHARE` (e.g., 30078)
- `tags`:
  - `["t", "hashscope"]`
  - `["run", "<RUN_ID>"]`
  - `["type", "share"]`
  - `["pool", "<POOL_ID_OR_HOST>"]` (optional)
  - `["schema", "hashscope.v1"]` (optional)
- `content`: JSON string with fields:
  - `schema`: `"hashscope.v1"`
  - `run_id`: string
  - `event_id`: uuid
  - `seq`: monotonically increasing integer (per run)
  - `ts`: ISO-8601 UTC timestamp
  - `pool`: `{ "host": "...", "port": 3333 }` (informational)
  - `stratum`: `{ "method": "mining.submit", "id": <id>, "params": [...] }`
  - `context`: optional decoded data useful for debug (worker name, extranonce sizes, etc.)
  - `raw`: optional base64 (if needed)

**Notes:**
- ShareEvent is a notification, not a guarantee
- Agents submit as-is (per-agent param modification is future work)

#### TelemetryEvent (agents → orchestrator)

Published by agents periodically and on notable events.

**Nostr event structure:**
- `kind`: `NOSTR_KIND_TELEMETRY` (e.g., 30079)
- `tags`:
  - `["t", "hashscope"]`
  - `["run", "<RUN_ID>"]`
  - `["type", "telemetry"]`
  - `["agent", "<AGENT_ID>"]`
  - `["pool", "<POOL_ID_OR_HOST>"]` (optional)
- `content`: JSON string with fields:
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

## MITM proxy behavior

### Core proxy functionality
1. Accept inbound miner connections (TCP).
2. Connect upstream to configured pool (TCP).
3. Relay messages bidirectionally, transparently (byte-for-byte at framing level).
4. Capture every message with direction, timestamp, raw bytes, and decoded JSON-RPC.
5. Never crash due to parsing errors; store parse errors with messages.
6. Maintain session state (per miner connection).

### Publishing ShareEvent
- Detect Stratum share submissions from real miner (typically `mining.submit`)
- Immediately publish ShareEvent to Nostr relay on a **background task**
- **Publishing must never block relaying**; if relay is down, queue up to a limit and drop oldest

### Subscribing to TelemetryEvent
- MITM backend connects to Nostr relay and maintains subscription for telemetry for `RUN_ID`
- Aggregate agent status and expose via local API for UI

---

## Agent fleet behavior

### Startup sequence
1. Load config (env vars + optional file)
2. Connect to target pool and perform standard Stratum handshake/auth:
   - `mining.subscribe`
   - `mining.authorize`
   - Request difficulty/work as needed by pool
3. Connect to Nostr relay WebSocket
4. Send REQ subscription for ShareEvent events for this `RUN_ID`:
   - Filter by tags: `hashscope` + `run_id` + `type=share`
   - Keep subscription open
5. Begin main loop:
   - On ShareEvent: submit to pool; record result; increment counters
   - Periodically publish TelemetryEvent (e.g., every 5s) and on notable errors

### Reconnect strategy

**If relay disconnects:**
- Exponential backoff reconnect (cap at ~30s)
- On reconnect, resubscribe with `since` = last_seen_ts - small overlap (e.g., 10s)

**If pool disconnects:**
- Reconnect and redo handshake
- Keep relay subscription alive

### Backpressure / safety
- Submitting to pool should be bounded:
  - If events arrive faster than agent can submit (unlikely), drop or buffer with max queue
- Telemetry is best-effort; never block submitting due to telemetry publishing

---

## Nostr protocol usage

### Keys
- MITM has a long-lived Nostr keypair (`MITM_NOSTR_SK`)
- Each agent has its own keypair (`AGENT_NOSTR_SK`) or one shared test keypair (allowed, but per-agent is preferred)
- All events must be signed

### Relay connections
- Use one primary relay URL (self-host preferred)
- Optional: secondary relay for redundancy
- Not part of docker-compose; assumed to be externally hosted

### Subscriptions (push, not polling)
Agents (and MITM for telemetry) open persistent WebSocket connections to relay and send REQ subscriptions:
- Filter by tags for `hashscope` + `run_id` + `type` (share or telemetry)
- Keep subscription open
- On reconnect, use `since` timestamp and/or last `seq` for catch-up

### Event kinds
Use custom kinds to keep filtering simple:
- `KIND_SHARE_EVENT` (e.g., 30078) — MITM publishes
- `KIND_TELEMETRY_EVENT` (e.g., 30079) — agents publish

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

---

## UI requirements

### Must have

**Session list:**
- Active + recent sessions
- Miner address, connect time, message count
- Clickable to filter message stream

**Message stream table:**
- Timestamp, direction badge, method, id, truncated params/result, size
- Live updates via WebSocket
- Pagination/history via REST

**Filters:**
- Session, direction, method, "errors only"
- Full-text search across decoded JSON and raw

**Detail drawer/panel:**
- Raw view (base64 or escaped string)
- Decoded JSON tree view
- Parse error display (if any)

**Agent fleet status:**
- Agent list with connection state
- Aggregated stats (shares received, submits attempted/accepted/rejected)
- Live telemetry updates via WebSocket

### Nice-to-have (if time permits)
- Latency view (recv→fwd)
- Per-method stats
- Export selected messages (JSON)
- Agent geographic map
- Per-agent detailed telemetry charts

---

## Docker / local dev

Preferred: `docker compose` for full stack.

### Services

Provide `docker-compose.yml` with:
- **backend** (MITM proxy + API)
- **frontend** (React UI)
- **agents** (scalable via replicas; env-based config)

**Exposed ports:**
- Proxy listen port (default 3333)
- API port (8000)
- UI port (3000/5173)

**Note:** Nostr relay is external (cloud); not part of compose.

### Required workflow after code changes

**CRITICAL:** After making ANY changes to backend, frontend, or agents code, you MUST:

1. **Always rebuild the Docker images** (only for the services you modified):
   - If you modified `backend/` code or `backend/requirements.txt`:
     ```bash
     docker compose build backend
     ```
   - If you modified `frontend/` code or `frontend/package.json`:
     ```bash
     docker compose build frontend
     ```
   - If you modified `agents/` code or `agents/requirements.txt`:
     ```bash
     docker compose build agents
     ```
   - If you modified multiple services, build each one separately or use `docker compose build backend frontend` etc.

2. **Update containers ONLY if they are currently running:**
   - First check if containers are running
   - If they ARE running, update them with:
     ```bash
     docker compose up -d
     ```
   - If they are NOT running, skip this step (just leave the newly built images ready for next start)

**When to rebuild:**
- After modifying Python code in `backend/` → build `backend`
- After modifying React/TypeScript code in `frontend/` → build `frontend`
- After modifying agent code in `agents/` → build `agents`
- After changing `requirements.txt`, `package.json`, or other dependency files → build the affected service
- After modifying a service's `Dockerfile` → build that service
- After modifying `docker-compose.yml` → may need to build affected services

**Complete refresh workflow** (if you need to start from scratch):
```bash
docker compose down
docker compose build
docker compose up -d
```

**Agents must check running container status before deciding whether to run `docker compose up -d` after building.**

---

## Commands (expected)

### Backend
- Install: `pip install -r backend/requirements.txt` (or `uv sync` if using uv)
- Run tests: `pytest -q`
- Run dev: `uvicorn hashscope.api.app:app --reload --host 0.0.0.0 --port 8000`
- Run proxy: `python -m hashscope.proxy.main` (or via API process if combined)

### Frontend
- Install: `npm ci` (or `pnpm i` if repo standard)
- Dev: `npm run dev`
- Build: `npm run build`
- Lint: `npm run lint`

### Agent
- Run: `python -m hashscope_agent.main`

### Docker
- Start all: `docker compose up -d`
- Stop all: `docker compose down`
- Rebuild: `docker compose build <service>`
- View logs: `docker compose logs -f <service>`

**If you introduce a new tool (uv, ruff, pnpm), add it to README and keep it consistent.**

---

## Coding standards

### Python
- Type hints required for public functions
- Prefer `ruff` + `black` if present; otherwise keep style consistent
- **No blocking calls in async code**
- Structured logging (JSON logs preferred)

### Frontend
- TypeScript strict mode preferred
- Keep components small; reuse shadcn primitives
- Proper error boundaries

### Security
- Treat all miner/pool data as untrusted input
- Never eval/execute received strings
- UI must escape content; render decoded JSON safely
- Keep Nostr event content minimal; avoid leaking secrets

### Nostr
- Use `RUN_ID` everywhere to prevent cross-talk
- Events must be signed
- Handle reconnects gracefully
- Never block proxy operations due to Nostr publishing

---

## Acceptance criteria

A feature or PR is "done" when:

### MITM Proxy
1. A miner can point to HashScope as a pool endpoint and successfully mine/connect (handshake works)
2. HashScope relays traffic correctly without corrupting messages (byte-for-byte relay at framing level)
3. Parsing failures are displayed but do not interrupt relaying
4. Web UI shows live messages with decoded JSON-RPC for Stratum v1 where applicable
5. MITM publishes ShareEvent when real miner submits a share
6. Publishing to relay never blocks MITM traffic relaying

### Agent Fleet
1. Agents connect to target pool and complete Stratum handshake/auth
2. Agents receive ShareEvent via subscription (push, no polling) immediately
3. Agents submit to pool and record responses correctly
4. Agents publish telemetry events; MITM aggregates and exposes via local API
5. System remains stable if relay disconnects (reconnect + resubscribe)
6. Agents handle backpressure (queue/drop excess events)

### UI
1. Message stream displays with filters and search
2. Session list shows active/recent miners
3. Detail panel shows raw + decoded + parse errors
4. Agent fleet status visible with live telemetry
5. `docker compose up -d` starts everything and UI loads

### Testing
1. Basic automated tests exist:
   - Parser unit tests
   - Session/capture logic tests
   - Schema validation for ShareEvent/TelemetryEvent
   - Nostr client reconnect logic (mock WebSocket)
   - Agent queue/backpressure behavior
   - (Optional) lightweight proxy integration test using fake upstream server

---

## What to do when unsure

- Prefer correctness + transparency over cleverness
- Never change message contents during relay (transparency is core requirement)
- If Stratum variants differ, implement best-effort decoding and keep raw bytes always
- Use `RUN_ID` to isolate concurrent test runs
- If using public relays, assume rate limits; self-host is recommended for predictable behavior
- Document assumptions in PR description and update README/this file if behavior changes
- When in doubt, ask for clarification rather than making breaking changes
