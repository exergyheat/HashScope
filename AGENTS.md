# AGENTS.md — HashScope

This file tells coding agents how to work in this repo: goals, architecture, conventions, how to run/test, and what “done” means.

## Project summary

**HashScope** is a man-in-the-middle (MITM) / proxy that sits between one or more Bitcoin miners and a mining pool. It relays traffic transparently while capturing and decoding Stratum messages for visualization and debugging.

- **Language:** Python (core proxy + API)
- **Runtime:** Docker-first
- **UI:** Web UI (modern React; prefer **shadcn/ui** components)
- **Transport to UI:** WebSocket (live stream) + REST (query/history/config)

## Iterations / scope

### Iteration 1 (MVP) — must implement first
1. Accept inbound miner connections (TCP).
2. Connect upstream to configured pool (TCP).
3. Relay messages bidirectionally.
4. Capture every message with:
   - direction (miner→pool / pool→miner)
   - timestamp (recv + send)
   - connection identity (miner id / session id)
   - raw payload (bytes)
   - decoded payload (JSON for Stratum v1; best-effort for others)
   - parse errors (if any)
5. Provide web UI to visualize:
   - live stream of messages
   - filtering by miner/session, method, direction
   - search
   - per-message detail panel with decoded fields

### Iteration 2 (future) — document only unless explicitly asked
- Relay selected messages to additional “shadow miner” endpoints.
- Configurable routing rules.
- UI for rule editing + toggles.

## Repo structure (recommended)

Agents should follow this layout unless it already exists:

- `backend/`
  - `hashscope/` (package)
    - `proxy/` (TCP proxy, sessions, relay)
    - `stratum/` (parsers/encoders, message models)
    - `capture/` (event model, storage)
    - `api/` (FastAPI app: REST + WS)
    - `config/` (pydantic settings)
  - `tests/` (pytest)
- `frontend/`
  - React app (next.js)
  - shadcn/ui components
- `docker/` (optional) or top-level `Dockerfile`, `docker-compose.yml`

If the repo already has a different structure, **adapt to it**—do not reorganize unless asked.

## Technology choices

### Backend
- **FastAPI** for REST + WebSocket.
- **asyncio** for TCP proxying (use `asyncio.start_server` + stream readers/writers).
- Structured logging (JSON logs) preferred.
- Parsing:
  - Stratum v1 commonly uses JSON-RPC over newline-delimited JSON.
  - Parse line-delimited JSON as primary; store raw bytes regardless.
  - Best-effort decoding; never crash the proxy due to parsing.

### Storage (Iteration 1)
Default: in-memory ring buffer per session + global index.
Optional: SQLite (only if asked); keep abstraction so it can be swapped later.

### Frontend
- React + TypeScript.
- **shadcn/ui** components for tables, tabs, dialogs, badges, dropdowns.
- Use WebSocket for live updates; paginate/history via REST.

## Configuration

Config should be possible via environment variables and a config file.

Minimum settings:
- `LISTEN_HOST` (default `0.0.0.0`)
- `LISTEN_PORT` (default `3333`)
- `POOL_HOST`
- `POOL_PORT` (default `3333` or pool-specific)
- `API_HOST` (default `0.0.0.0`)
- `API_PORT` (default `8000`)
- Capture:
  - `CAPTURE_MAX_MESSAGES` (default 50_000 total)
  - `CAPTURE_MAX_PER_SESSION` (default 10_000)

Agents must not hardcode pool endpoints.

## Message model

Every captured event must include:

- `id`: monotonic or UUID
- `ts_recv`: timestamp when received by HashScope
- `ts_fwd`: timestamp when forwarded (if forwarded)
- `direction`: `miner_to_pool` | `pool_to_miner`
- `session_id`: stable identifier per TCP miner connection
- `peer`: miner IP:port (and/or pool IP:port)
- `raw`: base64 or escaped string representation of bytes
- `decoded`: structured dict when parse succeeds (e.g., JSON-RPC fields)
- `parse_error`: string if decode fails

## UI requirements (Iteration 1)

Must have:
- Session list (active + recent), showing miner address, connect time, message count.
- Message stream table:
  - timestamp, direction badge, method, id, truncated params/result, size
- Filters:
  - session, direction, method, “errors only”
  - full-text search across decoded JSON and raw
- Detail drawer/panel:
  - raw view
  - decoded JSON tree view
  - parse error display (if any)

Nice-to-have (if time permits):
- latency view (recv→fwd)
- per-method stats
- export selected messages (JSON)

## Docker / local dev

Preferred: `docker compose` for full stack.

Agents should provide:
- `Dockerfile` for backend
- `Dockerfile` for frontend (or single multi-stage)
- `docker-compose.yml` with:
  - backend (TCP proxy + API)
  - frontend
  - exposed ports:
    - proxy listen port (default 3333)
    - API port (8000)
    - UI port (3000/5173)

## Commands (expected)

Backend:
- Install: `pip install -r backend/requirements.txt` (or `uv sync` if using uv)
- Run tests: `pytest -q`
- Run dev: `uvicorn hashscope.api.app:app --reload --host 0.0.0.0 --port 8000`
- Run proxy: `python -m hashscope.proxy.main` (or via API process if combined)

Frontend:
- Install: `npm ci` (or `pnpm i` if repo standard)
- Dev: `npm run dev`
- Build: `npm run build`
- Lint: `npm run lint`

If you introduce a new tool (uv, ruff, pnpm), **add it to README and keep it consistent**.

## Coding standards

- Python:
  - Type hints required for public functions.
  - Prefer `ruff` + `black` if present; otherwise keep style consistent.
  - No blocking calls in async code.
- Frontend:
  - TypeScript strict mode preferred.
  - Keep components small; reuse shadcn primitives.
- Security:
  - Treat all miner/pool data as untrusted input.
  - Never eval/execute received strings.
  - UI must escape content; render decoded JSON safely.

## Acceptance criteria for Iteration 1

A PR is “done” when:
1. A miner can point to HashScope as a pool endpoint and successfully mine/connect (handshake works).
2. HashScope relays traffic correctly without corrupting messages (byte-for-byte relay at the framing level).
3. Web UI shows live messages with decoded JSON-RPC for Stratum v1 where applicable.
4. Parsing failures are displayed but do not interrupt relaying.
5. `docker compose up` starts everything and the UI loads.
6. Basic automated tests exist:
   - parser unit tests
   - session/capture logic tests
   - (optional) a lightweight proxy integration test using a fake upstream server

## What to do when unsure

- Prefer correctness + transparency over cleverness.
- Never change message contents unless explicitly implementing Iteration 2 routing features.
- If Stratum variants differ, implement best-effort decoding and keep raw bytes always.
- Document assumptions in PR description and update README/this file if behavior changes.