# HashScope Quick Start Guide

## 🚀 5-Minute Setup

### Step 1: Set Your Pool Configuration

```bash
export POOL_HOST=stratum+tcp://your-pool.com
export POOL_PORT=3333
```

### Step 2: Start HashScope

```bash
./start.sh
```

Or manually:

```bash
docker-compose up -d
```

### Step 3: Point Your Miner

Instead of connecting directly to your pool, point your miner to HashScope:

```bash
# Before:
./miner --url stratum+tcp://pool.example.com:3333 --user your.worker

# After:
./miner --url stratum+tcp://localhost:3333 --user your.worker
```

### Step 4: View Messages

Open your browser to: **http://localhost:3000**

You'll see:
- Real-time message stream
- Decoded Stratum JSON-RPC messages
- Session management
- Filtering and search

## 📊 What You'll See

### Sessions Panel (Left)
- List of all connected miners
- Connection timestamps
- Message counts per session

### Messages Table (Center)
- Live stream of all messages
- Direction badges (Miner → Pool / Pool → Miner)
- Method names and parameters
- Parse status

### Message Detail (Bottom)
- Full decoded JSON view
- Raw message bytes
- Parse error details (if any)

### Filters (Top)
- Search across all messages
- Filter by direction
- Show errors only
- Filter by session

## 🔍 Common Use Cases

### Debug Connection Issues
1. Filter by session for the problematic miner
2. Look for error responses from pool
3. Check authorization messages

### Monitor Mining Efficiency
1. View `mining.notify` frequency
2. Check `mining.submit` responses
3. Monitor difficulty changes

### Analyze Pool Behavior
1. Filter "Pool → Miner" messages
2. Look at job notification patterns
3. Check pool response times

### Find Protocol Issues
1. Enable "Show Errors Only"
2. Review parse errors in detail panel
3. Check raw bytes for corrupted messages

## 📝 Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POOL_HOST` | **Yes** | - | Upstream pool (e.g., stratum+tcp://pool.com) |
| `POOL_PORT` | No | 3333 | Pool port |
| `LISTEN_PORT` | No | 3333 | Port for miners to connect to |
| `CAPTURE_MAX_MESSAGES` | No | 50000 | Max messages in memory |

## 🛠️ Useful Commands

```bash
# View logs
docker-compose logs -f

# View only backend logs
docker-compose logs -f backend

# Stop HashScope
docker-compose down

# Restart
docker-compose restart

# Rebuild after code changes
docker-compose up -d --build

# Check status
docker-compose ps
```

## ❓ Troubleshooting

### Miner can't connect
- Check port 3333 is not already in use: `lsof -i :3333`
- Verify firewall allows connections
- Check backend logs: `docker-compose logs backend`

### No messages appearing
- Ensure miner is connected to port 3333 (not directly to pool)
- Check WebSocket connection in browser console
- Verify `POOL_HOST` is correct

### "Disconnected" in UI
- Backend may be starting up (wait 10-20 seconds)
- Check backend is running: `docker-compose ps`
- Check for CORS errors in browser console

### Parse errors
- This is normal! Not all pools use standard Stratum v1
- Messages are still relayed correctly (transparent proxy)
- View raw bytes in detail panel to debug

## 🎯 Next Steps

1. **Run Tests**: `cd backend && pytest -q`
2. **Read Architecture**: See [AGENTS.md](AGENTS.md)
3. **Contribute**: See [CONTRIBUTING.md](CONTRIBUTING.md)
4. **API Docs**: http://localhost:8000/docs

## 📚 Learn More

- [Full README](README.md) - Complete documentation
- [AGENTS.md](AGENTS.md) - Architecture and development guide
- [API Docs](http://localhost:8000/docs) - REST API reference

---

**Need help?** Open an issue on GitHub!

