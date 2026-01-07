# HashScope Architecture Overview

## System Architecture

```
                                    ┌─────────────────────────────────────┐
                                    │         Mining Pool                  │
                                    │   (Upstream Stratum Server)         │
                                    └──────────────▲──────────────────────┘
                                                   │
                                                   │ TCP
                                                   │ (Relayed)
                                                   │
┌─────────────┐                    ┌──────────────┴──────────────────────┐
│   Miner 1   │────────┐           │                                      │
└─────────────┘        │           │        HashScope Backend             │
                       │           │      (Python + FastAPI)              │
┌─────────────┐        │ TCP       │                                      │
│   Miner 2   │────────┼──────────▶│  ┌────────────────────────────┐    │
└─────────────┘        │  :3333    │  │   TCP Proxy Server         │    │
                       │           │  │   (asyncio)                │    │
┌─────────────┐        │           │  └──────────┬─────────────────┘    │
│   Miner N   │────────┘           │             │                       │
└─────────────┘                    │             │ Captures              │
                                   │             ▼                       │
                                   │  ┌────────────────────────────┐    │
                                   │  │  Stratum Parser            │    │
                                   │  │  (JSON-RPC Decoder)        │    │
                                   │  └──────────┬─────────────────┘    │
                                   │             │                       │
                                   │             │ Parsed Messages       │
                                   │             ▼                       │
                                   │  ┌────────────────────────────┐    │
                                   │  │  Capture Storage           │    │
                                   │  │  (In-Memory Ring Buffer)   │    │
                                   │  └──────────┬─────────────────┘    │
                                   │             │                       │
                                   │             │ Stored Messages       │
                                   │             ▼                       │
                                   │  ┌────────────────────────────┐    │
                                   │  │  FastAPI Server            │    │
                                   │  │  REST + WebSocket          │    │
                                   │  │  :8000                     │    │
                                   │  └──────────┬─────────────────┘    │
                                   └─────────────┼───────────────────────┘
                                                 │
                                                 │ HTTP/WS
                                                 │
                                   ┌─────────────▼───────────────────────┐
                                   │     HashScope Frontend              │
                                   │     (React + TypeScript)            │
                                   │                                     │
                                   │  ┌────────────────────────────┐    │
                                   │  │   Session List             │    │
                                   │  └────────────────────────────┘    │
                                   │  ┌────────────────────────────┐    │
                                   │  │   Message Filters          │    │
                                   │  └────────────────────────────┘    │
                                   │  ┌────────────────────────────┐    │
                                   │  │   Message Table            │    │
                                   │  │   (Live Stream)            │    │
                                   │  └────────────────────────────┘    │
                                   │  ┌────────────────────────────┐    │
                                   │  │   Message Detail           │    │
                                   │  │   (Raw + Decoded)          │    │
                                   │  └────────────────────────────┘    │
                                   │                                     │
                                   │       Served by Nginx :80           │
                                   └─────────────────────────────────────┘
                                                 │
                                                 │ Browser
                                                 ▼
                                          ┌─────────────┐
                                          │    User     │
                                          └─────────────┘
```

## Data Flow

### 1. Miner → Pool (Upstream)

```
Miner sends message
        │
        ▼
  [TCP Socket :3333]
        │
        ▼
  ProxySession.relay_miner_to_pool()
        │
        ├─────────────────┐
        │                 │
        ▼                 ▼
  [Forward to Pool]  StratumParser.parse()
    (byte-for-byte)       │
                          ▼
                   CaptureStorage.add_message()
                          │
                          ▼
                   [In-Memory Buffer]
                          │
                          ▼
                   WebSocket.broadcast()
                          │
                          ▼
                    [UI Updates]
```

### 2. Pool → Miner (Downstream)

```
Pool sends response
        │
        ▼
  ProxySession.relay_pool_to_miner()
        │
        ├─────────────────┐
        │                 │
        ▼                 ▼
  [Forward to Miner]  StratumParser.parse()
    (byte-for-byte)       │
                          ▼
                   CaptureStorage.add_message()
                          │
                          ▼
                   [In-Memory Buffer]
                          │
                          ▼
                   WebSocket.broadcast()
                          │
                          ▼
                    [UI Updates]
```

## Component Responsibilities

### Backend Components

#### ProxyServer (`proxy/server.py`)
- Listen on TCP :3333
- Accept new miner connections
- Create ProxySession for each
- Manage session lifecycle

#### ProxySession (`proxy/session.py`)
- One per miner connection
- Connect to upstream pool
- Bidirectional relay (asyncio tasks)
- Capture messages before forwarding
- Handle disconnections gracefully

#### StratumParser (`stratum/parser.py`)
- Parse JSON-RPC messages
- Best-effort (never throws)
- Returns ParsedMessage with success/error
- Encode messages back to bytes

#### CaptureStorage (`capture/storage.py`)
- In-memory ring buffer
- Thread-safe with asyncio.Lock
- Per-session and global storage
- WebSocket subscription support
- Query with filters

#### FastAPI App (`api/app.py`)
- Starts ProxyServer in background
- Exposes REST endpoints
- WebSocket for real-time
- CORS middleware
- Lifespan management

### Frontend Components

#### App.tsx
- Main application state
- WebSocket connection
- Fetches sessions and messages
- Coordinates all child components

#### SessionList
- Displays all sessions
- Select session to filter
- Shows connection metadata

#### MessageFilters
- Search input
- Direction buttons
- Error toggle

#### MessageTable
- Scrollable message list
- Row selection
- Live updates from WebSocket

#### MessageDetail
- Full message metadata
- Tabbed decoded/raw view
- Parse error display

## Message Model

### CapturedMessage
```python
{
    "id": str,              # Unique message ID
    "ts_recv": datetime,     # When received by proxy
    "ts_fwd": datetime,      # When forwarded
    "direction": enum,       # miner_to_pool | pool_to_miner
    "session_id": str,       # Session identifier
    "peer": str,             # IP:port of peer
    "raw": str,              # Raw bytes (hex or text)
    "decoded": dict,         # Parsed JSON-RPC
    "parse_error": str,      # Error message if parse failed
    "size_bytes": int        # Message size
}
```

### Session Metadata
```python
{
    "session_id": str,
    "peer": str,
    "first_seen": datetime,
    "last_seen": datetime,
    "message_count": int,
    "stats": {
        "total_messages": int,
        "miner_to_pool": int,
        "pool_to_miner": int,
        "parse_errors": int
    }
}
```

## Technology Stack

### Backend
- **Python 3.11**
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
- **WebSocket API** - Real-time

### Infrastructure
- **Docker** - Containerization
- **docker-compose** - Orchestration
- **nginx** - Frontend serving + proxy

## Deployment Architecture

### Development
```
Developer Machine
├── Backend: http://localhost:8000
├── Frontend: http://localhost:5173 (Vite dev server)
└── Proxy: tcp://localhost:3333
```

### Production (Docker)
```
Docker Compose
├── hashscope-backend container
│   ├── Proxy: :3333
│   └── API: :8000
├── hashscope-frontend container
│   └── Nginx: :80 → serves UI + proxies /api to backend
└── hashscope network (bridge)
```

## Security Model

### Input Validation
- All miner/pool data treated as untrusted
- No string evaluation or code execution
- JSON parsing with error handling
- Type validation via Pydantic

### Network Isolation
- Docker network isolation
- CORS configured for known origins
- No default authentication (Iteration 1 scope)

### Data Handling
- In-memory only (no persistent storage)
- Ring buffer prevents memory exhaustion
- Automatic cleanup on overflow

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

## Extension Points (Iteration 2)

The architecture is designed to support future enhancements:

1. **Message Routing** - Add routing rules in ProxySession
2. **Shadow Miners** - Add additional upstream connections
3. **Persistent Storage** - Swap CaptureStorage implementation
4. **Authentication** - Add middleware to FastAPI
5. **Message Modification** - Add transform step before forwarding

## Monitoring & Observability

### Logging
- Structured JSON logs
- Per-session logging
- Connection lifecycle events
- Parse errors logged but non-fatal

### Metrics (Future)
- Messages per second
- Parse success rate
- Connection count
- Latency percentiles

### Debugging
- Web UI provides full message inspection
- Raw bytes always available
- Decode errors shown with context
- Session isolation for troubleshooting

---

This architecture prioritizes:
- **Reliability** - Never crash, always relay
- **Transparency** - Byte-perfect message forwarding
- **Visibility** - Complete message inspection
- **Simplicity** - Easy to understand and extend

