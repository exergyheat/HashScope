# HashScope

A man-in-the-middle (MITM) proxy for Bitcoin mining, sitting between miners and pools to capture, decode, and visualize Stratum protocol messages in real-time.

## Features

- **Transparent Proxy**: Relays traffic between miners and pools without corrupting messages
- **Real-time Capture**: Captures every message with full metadata
- **Stratum v1 Parsing**: Decodes JSON-RPC messages with best-effort parsing
- **Web Interface**: Modern React UI for visualizing message flow
- **WebSocket Streaming**: Live updates as messages flow through the proxy
- **Session Management**: Track multiple miner connections independently
- **Filtering & Search**: Filter by session, direction, method, or search across all data
- **Docker-First**: Easy deployment with docker-compose

## Quick Start

### Prerequisites

- Docker and Docker Compose
- An upstream mining pool to connect to

### Configuration

1. Set your upstream pool configuration:

```bash
export POOL_HOST=stratum+tcp://your-pool.com
export POOL_PORT=3333
```

Or create a `.env` file in the project root:

```env
POOL_HOST=stratum+tcp://your-pool.com
POOL_PORT=3333
```

### Run with Docker

```bash
docker-compose up -d
```

This will:
- Start the proxy server on port `3333` (point your miners here)
- Start the API server on port `8000`
- Start the web UI on port `3000` (open http://localhost:3000)

### Point Your Miners

Configure your miners to connect to HashScope instead of directly to the pool:

```bash
# Instead of: stratum+tcp://pool.example.com:3333
# Use: stratum+tcp://localhost:3333
```

HashScope will transparently relay all traffic to the configured upstream pool.

## Development

### Backend Development

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Set required environment variables
export POOL_HOST=stratum+tcp://your-pool.com
export POOL_PORT=3333

# Run tests
pytest -q

# Run the API server (includes proxy)
uvicorn hashscope.api.app:create_app --factory --reload --host 0.0.0.0 --port 8000

# Or run proxy standalone
python -m hashscope.proxy.main
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm ci

# Run dev server
npm run dev

# Build for production
npm run build

# Lint
npm run lint
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
```

### Components

- **Backend** (`backend/hashscope/`)
  - `proxy/` - TCP proxy server and session management
  - `stratum/` - Stratum v1 protocol parser
  - `capture/` - Message capture and in-memory storage
  - `api/` - FastAPI REST + WebSocket endpoints
  - `config/` - Configuration management

- **Frontend** (`frontend/src/`)
  - Modern React + TypeScript
  - shadcn/ui components
  - WebSocket for real-time updates
  - REST API for queries and history

## API Documentation

Once running, visit:
- **API Docs**: http://localhost:8000/docs
- **Web UI**: http://localhost:3000

### REST Endpoints

- `GET /api/sessions` - List all sessions
- `GET /api/sessions/{id}` - Get session details and stats
- `GET /api/messages` - List messages (with filters)
- `GET /api/messages/{id}` - Get specific message

### WebSocket

- `WS /api/ws` - Real-time message stream

## Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `LISTEN_HOST` | `0.0.0.0` | Proxy listen address |
| `LISTEN_PORT` | `3333` | Proxy listen port |
| `POOL_HOST` | **required** | Upstream pool hostname |
| `POOL_PORT` | `3333` | Upstream pool port |
| `API_HOST` | `0.0.0.0` | API server address |
| `API_PORT` | `8000` | API server port |
| `CAPTURE_MAX_MESSAGES` | `50000` | Max total messages in memory |
| `CAPTURE_MAX_PER_SESSION` | `10000` | Max messages per session |

## Message Model

Every captured message includes:

```json
{
  "id": "session-id-123",
  "ts_recv": "2024-01-07T12:34:56.789Z",
  "ts_fwd": "2024-01-07T12:34:56.791Z",
  "direction": "miner_to_pool",
  "session_id": "abc-def-123",
  "peer": "192.168.1.100:12345",
  "raw": "{\"id\":1,\"method\":\"mining.subscribe\"}",
  "decoded": {
    "id": 1,
    "method": "mining.subscribe",
    "params": ["cpuminer/2.5.0"]
  },
  "parse_error": null,
  "size_bytes": 52
}
```

## Testing

```bash
cd backend
pytest -q
```

Tests cover:
- Stratum protocol parsing
- Message capture and storage
- Session management

## Limitations (Iteration 1)

- **In-memory storage only**: Messages are lost on restart
- **No authentication**: Anyone can access the UI
- **Stratum v1 only**: Best-effort parsing; other protocols show raw data
- **No message modification**: Pure relay (see AGENTS.md for Iteration 2 plans)

## Troubleshooting

### Miners can't connect

- Check that port 3333 is accessible
- Verify `POOL_HOST` and `POOL_PORT` are set correctly
- Check backend logs: `docker-compose logs backend`

### Web UI shows "Disconnected"

- Ensure backend is running
- Check browser console for WebSocket errors
- Verify CORS settings if accessing from different origin

### Parse errors

- HashScope uses best-effort parsing
- Parse errors are captured and displayed but don't interrupt relay
- Check message detail panel for specific error information

## Contributing

See [AGENTS.md](AGENTS.md) for development guidelines and architecture details.

## License

Copyright © 2024 256 Foundation

