#!/bin/bash
# Quick start script for HashScope

set -e

echo "🔍 HashScope - Bitcoin Mining MITM Proxy"
echo ""

# Check if POOL_HOST is set
if [ -z "$POOL_HOST" ]; then
    echo "⚠️  Warning: POOL_HOST environment variable is not set"
    echo ""
    echo "Please set your upstream pool configuration:"
    echo "  export POOL_HOST=stratum+tcp://your-pool.com"
    echo "  export POOL_PORT=3333"
    echo ""
    read -p "Do you want to continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "🐳 Starting HashScope with docker-compose..."
echo ""

docker-compose up --build -d

echo ""
echo "✅ HashScope is starting!"
echo ""
echo "Services:"
echo "  • Proxy (miners connect here):  localhost:3333"
echo "  • API Server:                   http://localhost:8000"
echo "  • Web UI:                       http://localhost:3000"
echo "  • API Docs:                     http://localhost:8000/docs"
echo ""
echo "View logs:"
echo "  docker-compose logs -f"
echo ""
echo "Stop services:"
echo "  docker-compose down"
echo ""

