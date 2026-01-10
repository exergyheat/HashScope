# API Reference

Once HashScope is running, the API is available at **http://localhost:8000**

Interactive API documentation: **http://localhost:8000/docs**

## REST Endpoints

### Sessions

#### GET /api/sessions

List all miner sessions.

**Response:**
```json
[
  {
    "session_id": "abc-def-123",
    "peer": "192.168.1.100:12345",
    "first_seen": "2024-01-07T12:34:56.789Z",
    "last_seen": "2024-01-07T12:45:00.123Z",
    "message_count": 156,
    "stats": {
      "total_messages": 156,
      "miner_to_pool": 78,
      "pool_to_miner": 78,
      "parse_errors": 0
    }
  }
]
```

#### GET /api/sessions/{id}

Get details for a specific session.

**Response:**
```json
{
  "session_id": "abc-def-123",
  "peer": "192.168.1.100:12345",
  "first_seen": "2024-01-07T12:34:56.789Z",
  "last_seen": "2024-01-07T12:45:00.123Z",
  "message_count": 156,
  "stats": {
    "total_messages": 156,
    "miner_to_pool": 78,
    "pool_to_miner": 78,
    "parse_errors": 0
  }
}
```

### Messages

#### GET /api/messages

List captured messages with optional filters.

**Query Parameters:**
- `session_id` (optional) - Filter by session
- `direction` (optional) - Filter by direction (`miner_to_pool`, `pool_to_miner`, `hashscope_to_pool`)
- `limit` (optional) - Max messages to return (default 100)

**Response:**
```json
[
  {
    "id": "msg-123",
    "ts_recv": "2024-01-07T12:34:56.789Z",
    "ts_fwd": "2024-01-07T12:34:56.791Z",
    "direction": "miner_to_pool",
    "session_id": "abc-def-123",
    "peer": "192.168.1.100:12345",
    "raw": "{\"id\":1,\"method\":\"mining.subscribe\"}\n",
    "decoded": {
      "id": 1,
      "method": "mining.subscribe",
      "params": ["cpuminer/2.5.0"]
    },
    "parse_error": null,
    "size_bytes": 52
  }
]
```

#### GET /api/messages/{id}

Get a specific message by ID.

**Response:** Same as single message in array above.

### Agents

#### GET /api/agents

List all agents and their telemetry.

**Response:**
```json
[
  {
    "agent_id": "agent-us-west-1",
    "pool_target": {"host": "pool.example.com", "port": 3333},
    "conn_state": "connected",
    "last_seen": "2024-01-07T12:34:56.789Z",
    "stats": {
      "share_events_received_total": 1523,
      "submits_attempted_total": 1520,
      "submits_accepted_total": 1450,
      "submits_rejected_total": 70,
      "last_submit_latency_ms": 42
    }
  }
]
```

## WebSocket

### WS /api/ws

Real-time message stream.

**Protocol:**
- Connect to `ws://localhost:8000/api/ws`
- Server pushes messages as JSON
- Each message is same format as REST API message object
- Connection auto-reconnects on disconnect

**Example (JavaScript):**
```javascript
const ws = new WebSocket('ws://localhost:8000/api/ws');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('New message:', message);
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket closed, reconnecting...');
};
```

## Configuration Endpoints

### GET /api/config

Get current HashScope configuration (non-sensitive fields only).

**Response:**
```json
{
  "listen_host": "0.0.0.0",
  "listen_port": 3333,
  "pool_host": "stratum+tcp://pool.example.com",
  "pool_port": 3333,
  "api_port": 8000,
  "capture_max_messages": 50000,
  "nostr_enabled": true,
  "run_id": "test-run-123"
}
```

## Error Responses

All endpoints return standard HTTP status codes:

- **200** - Success
- **404** - Resource not found
- **422** - Validation error
- **500** - Internal server error

**Error format:**
```json
{
  "detail": "Error message"
}
```

