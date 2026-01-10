# Developer Guide

## Project Structure

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
│   │   ├── pages/           # Route pages
│   │   └── lib/             # API client, utilities
│   └── package.json
└── docker-compose.yml
```

## Technology Stack

### Backend
- **Python 3.11+**
- **FastAPI** - Web framework
- **asyncio** - Async I/O for TCP
- **Pydantic** - Data validation
- **uvicorn** - ASGI server
- **pytest** - Testing

### Frontend
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **shadcn/ui** - Component library
- **Tailwind CSS** - Styling
- **React Router** - Routing
- **Mermaid** - Diagrams

### Infrastructure
- **Docker** - Containerization
- **docker-compose** - Orchestration
- **nginx** - Frontend serving

## Development Setup

### Backend

```bash
cd backend
pip install -r requirements.txt

# Set required config
export POOL_HOST=stratum+tcp://your-test-pool.com
export POOL_PORT=3333

# Run tests
pytest -q

# Run in development
uvicorn hashscope.api.app:create_app --factory --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Frontend dev server runs on http://localhost:5173 and proxies API requests to backend.

### Agent

```bash
cd agents
pip install -r requirements.txt

# Set config
export AGENT_POOL_HOST=stratum+tcp://pool.example.com
export AGENT_NOSTR_RELAY_URL=wss://relay.damus.io
export AGENT_RUN_ID=test-run-123
export AGENT_WORKER_NAME=test_agent

# Run agent
python -m hashscope_agent.main
```

## Coding Standards

### Python
- Type hints required for public functions
- Use `ruff` or `black` for formatting
- **No blocking calls in async code**
- Structured logging (JSON logs preferred)
- Best-effort parsing - never crash on malformed input

### TypeScript
- Strict mode enabled
- Functional components with hooks
- Prefer composition over complex components
- Type all props and state

### Key Principles

1. **Never modify message contents** - byte-for-byte relay
2. **Best-effort parsing** - parse errors should not crash the proxy
3. **Security first** - treat all input as untrusted
4. **Type safety** - use type hints and TypeScript strictly
5. **Nostr events must be signed** - all events require valid signatures
6. **Publishing never blocks relaying** - background tasks only

## Message Model

### CapturedMessage

```python
{
    "id": str,              # Unique message ID
    "ts_recv": datetime,     # When received by proxy
    "ts_fwd": datetime,      # When forwarded
    "direction": enum,       # miner_to_pool | pool_to_miner | hashscope_to_pool
    "session_id": str,       # Session identifier
    "peer": str,             # IP:port of peer
    "raw": str,              # Raw bytes (escaped string or base64)
    "decoded": dict,         # Parsed JSON-RPC
    "parse_error": str,      # Error message if parse failed
    "size_bytes": int        # Message size
}
```

## Testing

```bash
# Backend tests
cd backend
pytest -q

# Run specific test
pytest tests/test_stratum_parser.py -v

# Frontend lint
cd frontend
npm run lint
```

## Docker Workflow

**CRITICAL**: After making ANY code changes, rebuild affected services:

```bash
# Modified backend code or requirements.txt
docker compose build backend

# Modified frontend code or package.json
docker compose build frontend

# Modified agent code
docker compose build agents

# Update running containers
docker compose up -d

# Complete refresh
docker compose down
docker compose build
docker compose up -d
```

## Performance Characteristics

### Scalability
- **Concurrent miners**: Limited by system resources
- **Messages/second**: Thousands (async I/O)
- **Memory usage**: Bounded by ring buffer size
- **CPU usage**: Low (mostly I/O bound)

### Latency
- **Relay overhead**: <1ms (in-memory copy)
- **Parse overhead**: ~0.1ms per message
- **WebSocket broadcast**: <10ms to all clients

## Extension Points

The architecture supports future enhancements:

1. **Message Routing** - Add routing rules in ProxySession
2. **Persistent Storage** - Swap CaptureStorage implementation
3. **Authentication** - Add middleware to FastAPI
4. **Message Modification** - Add transform step before forwarding (future iterations)
5. **Additional Relays** - Secondary Nostr relays for redundancy

