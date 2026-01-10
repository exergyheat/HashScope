# HashScope

A man-in-the-middle (MITM) proxy for Bitcoin mining, sitting between miners and pools to capture, decode, and visualize Stratum protocol messages in real-time.

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

## What is HashScope?

HashScope allows you to inspect and debug Bitcoin mining pool communication by transparently intercepting Stratum protocol messages. Point your miners at HashScope instead of directly at your pool, and HashScope will relay all traffic while capturing and decoding every message for analysis.

Perfect for:
- Debugging miner connection issues
- Understanding pool behavior
- Analyzing share submission patterns
- Protocol debugging and development
- Load testing mining pools with distributed agents

