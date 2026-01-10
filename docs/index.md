# HashScope Documentation

A man-in-the-middle (MITM) proxy for Bitcoin mining, sitting between miners and pools to capture, decode, and visualize Stratum protocol messages in real-time.

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } __Quick Start__

    ---

    Get started in 5 minutes

    [:octicons-arrow-right-24: Quick Start Guide](quickstart.md)

-   :material-transit-connection-variant:{ .lg .middle } __Architecture__

    ---

    Understand the system design

    [:octicons-arrow-right-24: System Architecture](architecture.md)

-   :material-network:{ .lg .middle } __Agent Fleet__

    ---

    Distributed testing with Nostr

    [:octicons-arrow-right-24: Agent Fleet Guide](agent-fleet.md)

-   :material-code-braces:{ .lg .middle } __Developer Guide__

    ---

    Development setup and standards

    [:octicons-arrow-right-24: Developer Guide](developer-guide.md)

</div>

## Key Features

- **Transparent Proxy**: Relays traffic between miners and pools without corrupting messages
- **Real-time Capture**: Captures every message with full metadata
- **Stratum v1 Parsing**: Decodes JSON-RPC messages with best-effort parsing
- **Web Interface**: Modern React UI for visualizing message flow
- **WebSocket Streaming**: Live updates as messages flow through the proxy
- **Session Management**: Track multiple miner connections independently
- **Filtering & Search**: Filter by session, direction, method, or search across all data
- **Distributed Agent Fleet**: Scale load testing across multiple agents via Nostr relay
- **Real-time Telemetry**: Monitor agent performance and pool responses

## Getting Started

```bash
# Set your pool configuration
export POOL_HOST=stratum+tcp://your-pool.com
export POOL_PORT=3333

# Start HashScope
docker compose up -d

# Point your miner to localhost:3333
# Open http://localhost:3000 in your browser
```

For complete setup instructions, see the [Quick Start Guide](quickstart.md).

## Features

This documentation includes:

- **Interactive Mermaid diagrams** for system architecture visualization
- **Code syntax highlighting** with copy-to-clipboard
- **Full-text search** across all documentation
- **Dark/Light mode** support
- **Mobile responsive** design

## Repository

- **GitHub**: [https://github.com/256foundation/HashScope](https://github.com/256foundation/HashScope)
- **Issues**: [https://github.com/256foundation/HashScope/issues](https://github.com/256foundation/HashScope/issues)

## License

Copyright © 2024 256 Foundation

