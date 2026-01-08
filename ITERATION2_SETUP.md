# Iteration 2 Setup Guide

This guide will help you set up and test the Iteration 2 features (Nostr Agent Fleet).

## Prerequisites

1. Docker and Docker Compose installed
2. Access to a Nostr relay (public or self-hosted)
3. A Bitcoin mining pool for testing (your own preferred)

## Quick Start

### 1. Configure Environment (Nostr keys are auto-generated if not provided)

Create a `.env` file in the project root:

```bash
# Pool configuration
POOL_HOST=stratum+tcp://your-pool.example.com
POOL_PORT=3333

# Nostr configuration
RUN_ID=test-run-$(date +%s)
NOSTR_ENABLED=true
NOSTR_RELAY_URL=wss://relay.damus.io
# NOSTR_SK=<optional-mitm-private-key-hex>  # Auto-generated if not provided

# Agent configuration
# AGENT_NOSTR_SK=<optional-agent-private-key-hex>  # Auto-generated if not provided
AGENT_WORKER_NAME=hashscope_test_agent
AGENT_WORKER_PASSWORD=x
```

**Note:** Nostr private keys (`NOSTR_SK` and `AGENT_NOSTR_SK`) are optional. If not provided, they will be auto-generated at startup. The generated keys will be logged - save them if you want to reuse them across restarts.

### 3. Start the System

```bash
# Start MITM and frontend
docker compose up -d backend frontend

# Start 3 agents
docker compose up -d --scale=3 agent
```

### 4. Check Generated Keys

If you didn't provide keys, check the logs for the auto-generated ones:

```bash
# Check MITM logs for generated key
docker compose logs backend | grep "Generated new Nostr private key"

# Check agent logs for generated keys
docker compose logs agent | grep "Generated new Nostr private key"
```

Save these keys to your `.env` file if you want to persist them.

### 5. Test the System

```bash
# Run integration tests
./test_iteration2.sh
```

## Using the System

### Enable Broadcast for a Session

1. Connect a miner to `localhost:3333`
2. Open the UI at `http://localhost:3000`
3. In the Sessions panel, toggle "Broadcast to Agents" to ON
4. The session will now forward share submissions to all agents

### Monitor Agents

- **UI**: Check the "Agent Fleet" panel to see agent status
- **API**: `curl http://localhost:8000/api/agents | jq`
- **Logs**: `docker compose logs -f agent`

### Agent Telemetry

Each agent publishes telemetry every 5 seconds including:
- Connection state (connected/reconnecting/error)
- Share events received
- Submits attempted/accepted/rejected
- Last submit latency

## Architecture

```
┌─────────┐         ┌──────────┐         ┌──────┐
│  Miner  │────────▶│   MITM   │────────▶│ Pool │
└─────────┘         └──────────┘         └──────┘
                         │                    ▲
                         │ Nostr             │
                         ▼ (ShareEvent)      │
                    ┌──────────┐            │
                    │  Nostr   │            │
                    │  Relay   │            │
                    └──────────┘            │
                         │                  │
                         │ Subscribe        │ Submit
                         ▼                  │
                    ┌──────────┐           │
                    │ Agent 1  │───────────┘
                    │ Agent 2  │───────────┘
                    │ Agent N  │───────────┘
                    └──────────┘
                         │
                         │ Telemetry
                         ▼
                    ┌──────────┐
                    │   MITM   │────▶ UI
                    └──────────┘
```

## Configuration Details

### MITM Proxy

Environment variables:
- `NOSTR_ENABLED`: Enable/disable Nostr functionality (default: false)
- `NOSTR_RELAY_URL`: Primary Nostr relay URL
- `NOSTR_SK`: Hex-encoded private key for MITM (auto-generated if not provided)
- `RUN_ID`: Unique identifier for this run (isolates event streams, auto-generated if not provided)

### Agents

Environment variables (note `AGENT_` prefix):
- `AGENT_POOL_HOST`: Pool to connect to
- `AGENT_POOL_PORT`: Pool port
- `AGENT_WORKER_NAME`: Worker/miner name for pool auth
- `AGENT_WORKER_PASSWORD`: Worker password
- `AGENT_NOSTR_RELAY_URL`: Nostr relay URL
- `AGENT_NOSTR_SK`: Hex-encoded private key for agent (auto-generated if not provided)
- `AGENT_RUN_ID`: Must match MITM's RUN_ID
- `AGENT_TELEMETRY_INTERVAL_SEC`: Telemetry publishing interval (default: 5)

## Troubleshooting

### Agents not receiving shares

1. Check that `RUN_ID` matches between MITM and agents
2. Verify Nostr relay is accessible: `curl -I https://relay.damus.io`
3. Check MITM logs: `docker compose logs backend`
4. Ensure broadcast is enabled for the session

### Agents not connecting to pool

1. Check pool host and port configuration
2. Verify worker name and password
3. Check agent logs: `docker compose logs agent`

### No telemetry in UI

1. Check that agents are running: `docker compose ps`
2. Verify Nostr relay connectivity
3. Check browser console for errors
4. Refresh the UI page

## Security Notes

- Keep your Nostr private keys (`NOSTR_SK`, `AGENT_NOSTR_SK`) secret
- Auto-generated keys are ephemeral - they change on restart unless you save them to `.env`
- Use unique `RUN_ID` for each test run to prevent cross-talk
- When using public Nostr relays, be aware that events are publicly visible
- For production, self-host your Nostr relay and use persistent keys

## Stopping the System

```bash
# Stop all services
docker compose down

# Stop and remove volumes
docker compose down -v
```

## Next Steps

- Scale agents: `docker compose up -d --scale agent=N`
- Monitor performance: Check agent latency and accept/reject ratios
- Customize telemetry interval in agent config
- Set up your own Nostr relay for better control

