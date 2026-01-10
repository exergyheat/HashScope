# HashScope

A Bitcoin mining analysis platform with transparent MITM proxy and distributed agent fleet for capturing, analyzing, and testing mining pool behavior.

## Features

- **Transparent Proxy**: Relays traffic between miners and pools without corrupting messages
- **Real-time Capture**: Captures every message with full metadata
- **Stratum v1 Parsing**: Decodes JSON-RPC messages with best-effort parsing
- **Web Interface**: Modern React UI for visualizing message flow and agent telemetry
- **Distributed Agents**: Scalable fleet of agents that receive share events and submit to pools for analysis
- **Nostr Integration**: Push-based event distribution via Nostr relay (no polling)
- **Session Management**: Track multiple miner connections independently
- **Filtering & Search**: Filter by session, direction, method, or search across all data
- **Docker-First**: Easy deployment with docker-compose

## Quick Start

### Prerequisites

- Docker and Docker Compose
- An upstream mining pool to connect to
- (Optional) Nostr relay URL for distributed agent features

### Configuration

Create a `.env` file in the project root (copy from `env.example`):

```bash
cp env.example .env
```

Edit the `.env` file and set at minimum:

```env
POOL_HOST=stratum+tcp://your-pool.com
POOL_PORT=3333
```

For distributed agent features (Iteration 2), also configure:

```env
NOSTR_ENABLED=true
NOSTR_RELAY_URL=wss://relay.example.com
RUN_ID=test-run-$(date +%s)
WORKER_NAME=your_worker_name
```

### Run with Docker

```bash
docker compose up -d
```

This will start:
- **Backend**: Proxy server on port `3333` + API server on port `8000`
- **Frontend**: Web UI on port `3000` (open http://localhost:3000)
- **Agents**: Configurable number of distributed agents (when Nostr enabled)

### Point Your Miners

Configure your miners to connect to HashScope instead of directly to the pool:

```bash
# Instead of: stratum+tcp://pool.example.com:3333
# Use: stratum+tcp://localhost:3333
```

HashScope will transparently relay all traffic to the configured upstream pool.

### View Logs

```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f agents
```

### Stop Services

```bash
docker compose down
```

## Architecture

```
┌─────────┐      ┌──────────────┐      ┌──────────┐
│ Miner 1 │─────▶│              │─────▶│          │
└─────────┘      │              │      │ Mining   │
                 │  HashScope   │      │  Pool    │
┌─────────┐      │    Proxy     │      │          │
│ Miner 2 │─────▶│              │◀─────│          │
└─────────┘      └──────┬───────┘      └──────────┘
                        │
                        │ Capture & Decode
                        │
                        ▼
                 ┌──────────────┐
                 │   Web UI     │
                 │  (Browser)   │
                 └──────────────┘
                        ▲
                        │ Telemetry
                        │
            ┌───────────┴───────────┐
            │                       │
      ┌─────▼──────┐        ┌──────▼─────┐
      │  Agent 1   │   ...  │  Agent N   │
      │ (Region A) │        │ (Region N) │
      └────────────┘        └────────────┘
            │                       │
            └───────────┬───────────┘
                        │
                        ▼
                 ┌──────────────┐
                 │ Nostr Relay  │
                 │   (Cloud)    │
                 └──────────────┘
```

## Components

### Backend (`backend/hashscope/`)

The backend is a Python-based FastAPI application that handles all core functionality:

- **Proxy (`proxy/`)**: Transparent TCP proxy that sits between miners and pools, relaying Stratum traffic byte-for-byte while capturing every message. Accepts inbound miner connections and maintains upstream pool connections with full session management.

- **Stratum Parser (`stratum/`)**: Decodes Stratum v1 JSON-RPC protocol messages with best-effort parsing. Handles line-delimited JSON and maintains message structure even when parsing fails.

- **Capture System (`capture/`)**: In-memory message storage with configurable ring buffers per session and global limits. Stores both raw bytes and decoded JSON-RPC structures with full metadata (timestamps, direction, peer info).

- **API (`api/`)**: FastAPI REST endpoints and WebSocket server for the web UI. Provides real-time message streaming, session management, filtering, search, and agent fleet status aggregation.

- **Nostr Integration (`nostr/`)**: Publishes share events when miners submit shares and subscribes to agent telemetry. Uses push-based WebSocket subscriptions (no polling) with automatic reconnection and catch-up logic.

- **Configuration (`config/`)**: Pydantic-based settings management with environment variable support and validation.

### Frontend (`frontend/`)

Modern React + TypeScript web application for visualization and monitoring:

- Built with **Vite** for fast development and optimized production builds
- **shadcn/ui** component library for consistent, beautiful UI elements
- **Real-time updates** via WebSocket connection to backend
- **Message stream visualization** with filtering, search, and detail views
- **Session management** with live/recent session tracking
- **Agent fleet dashboard** showing connection status, statistics, and telemetry
- **Responsive design** that works on desktop and mobile devices

### Agents (`agents/hashscope_agent/`)

Distributed Python agents that form a scalable testing fleet:

- **Pool Client (`pool_client.py`)**: Full Stratum client implementation that connects to target pools, performs handshake/auth, and submits shares exactly as a real miner would.

- **Nostr Client (`nostr_client.py`)**: Maintains persistent WebSocket subscription to Nostr relay for share events. Uses push-based delivery (no polling) with automatic reconnection and event catch-up on disconnect.

- **Share Submission**: Receives share events from the MITM proxy via Nostr, submits them to the configured pool, and records acceptance/rejection results with latency measurements.

- **Telemetry Publishing**: Reports agent health, connection status, submission statistics, and errors back to the orchestrator via Nostr relay at configurable intervals.

- **Multi-Region Deployment**: Designed to run in multiple geographic regions for comprehensive pool testing and latency analysis.

## Access the Application

Once running, visit:
- **Web UI**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs (interactive API documentation)

## Configuration Options

All configuration is done via environment variables. Copy `env.example` to `.env` and customize as needed.

### Core Settings

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `POOL_HOST` | - | **Yes** | Upstream pool hostname (e.g., `stratum+tcp://your-pool.com`) |
| `POOL_PORT` | `3333` | No | Upstream pool port |
| `LISTEN_HOST` | `0.0.0.0` | No | Proxy listen address (for miner connections) |
| `LISTEN_PORT` | `3333` | No | Proxy listen port (point your miners here) |
| `API_HOST` | `0.0.0.0` | No | API server listen address |
| `API_PORT` | `8000` | No | API server port |

### Capture Settings

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `CAPTURE_MAX_MESSAGES` | `50000` | No | Maximum total messages stored in memory |
| `CAPTURE_MAX_PER_SESSION` | `10000` | No | Maximum messages stored per miner session |

### Nostr Configuration (Iteration 2)

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `NOSTR_ENABLED` | `false` | No | Enable distributed agent features via Nostr relay |
| `RUN_ID` | auto-generated | Conditional | Unique run identifier; same value must be used by MITM and all agents to communicate. Required when `NOSTR_ENABLED=true` |
| `NOSTR_RELAY_URL` | - | Conditional | Nostr relay WebSocket URL (e.g., `wss://relay.damus.io`). Required when `NOSTR_ENABLED=true` |
| `NOSTR_SK` | auto-generated | No | Nostr private key for MITM (hex-encoded). Auto-generated if not provided; save from logs to persist |
| `NOSTR_KIND_SHARE` | `30080` | No | Custom Nostr event kind for share events |
| `NOSTR_KIND_TELEMETRY` | `30079` | No | Custom Nostr event kind for agent telemetry |

### Agent Configuration

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `WORKER_NAME` | `hashscope_agent` | No | Worker name for pool authentication. Agents append `.hashscope_agent{random}` for uniqueness |
| `WORKER_PASSWORD` | `x` | No | Worker password (if required by pool) |
| `TELEMETRY_INTERVAL_SEC` | `5` | No | How often agents publish telemetry events (in seconds) |

## Testing

Run the test suite with Docker:

```bash
# Run backend tests
docker compose run --rm backend pytest -q

# Run with verbose output
docker compose run --rm backend pytest -v
```

Tests cover:
- Stratum protocol parsing and message models
- Message capture and storage with ring buffers
- Session management and broadcasting
- Nostr event schemas and constants
- Agent statistics tracking

## Troubleshooting

### Miners can't connect

- Check that port 3333 is accessible
- Verify `POOL_HOST` and `POOL_PORT` are set correctly
- Check backend logs: `docker compose logs backend`

### Web UI shows "Disconnected"

- Ensure backend is running
- Check browser console for WebSocket errors
- Verify CORS settings if accessing from different origin

### Parse errors

- HashScope uses best-effort parsing
- Parse errors are captured and displayed but don't interrupt relay
- Check message detail panel for specific error information

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

For complete architecture and development details, visit the **[interactive documentation](http://localhost:3000/docs)** or read:
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [AGENTS.md](AGENTS.md) - Developer guide and conventions
- [ITERATION2_SETUP.md](ITERATION2_SETUP.md) - Agent fleet setup

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright © 2024 256 Foundation

