#!/bin/bash
# Integration test script for Iteration 2

set -e

echo "========================================="
echo "HashScope Iteration 2 Integration Test"
echo "========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
API_BASE="http://localhost:8000/api"
TEST_SESSION_ID=""

echo -e "${YELLOW}Prerequisites:${NC}"
echo "1. MITM backend must be running with Nostr enabled"
echo "2. Nostr relay must be accessible"
echo "3. At least one miner session should be active"
echo ""

# Function to check if backend is running
check_backend() {
    echo -e "${YELLOW}Checking if backend is running...${NC}"
    if curl -s "${API_BASE}/../health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend is running${NC}"
        return 0
    else
        echo -e "${RED}✗ Backend is not running${NC}"
        echo "Please start the backend with: docker compose up -d backend"
        exit 1
    fi
}

# Function to get active sessions
get_sessions() {
    echo -e "${YELLOW}Fetching active sessions...${NC}"
    SESSIONS=$(curl -s "${API_BASE}/sessions")
    SESSION_COUNT=$(echo "$SESSIONS" | jq '. | length')

    if [ "$SESSION_COUNT" -eq 0 ]; then
        echo -e "${RED}✗ No active sessions found${NC}"
        echo "Please connect a miner to localhost:3333"
        exit 1
    fi

    echo -e "${GREEN}✓ Found $SESSION_COUNT active session(s)${NC}"
    TEST_SESSION_ID=$(echo "$SESSIONS" | jq -r '.[0].session_id')
    echo "Using session: $TEST_SESSION_ID"
}

# Function to check broadcast status
check_broadcast_status() {
    echo -e "${YELLOW}Checking broadcast status for session $TEST_SESSION_ID...${NC}"
    STATUS=$(curl -s "${API_BASE}/sessions/${TEST_SESSION_ID}/broadcast/status")
    ENABLED=$(echo "$STATUS" | jq -r '.broadcast_enabled')

    if [ "$ENABLED" = "true" ]; then
        echo -e "${GREEN}✓ Broadcast is enabled${NC}"
    else
        echo -e "${YELLOW}○ Broadcast is disabled${NC}"
    fi
}

# Function to enable broadcast
enable_broadcast() {
    echo -e "${YELLOW}Enabling broadcast for session $TEST_SESSION_ID...${NC}"
    RESPONSE=$(curl -s -X POST "${API_BASE}/sessions/${TEST_SESSION_ID}/broadcast/enable")
    ENABLED=$(echo "$RESPONSE" | jq -r '.broadcast_enabled')

    if [ "$ENABLED" = "true" ]; then
        echo -e "${GREEN}✓ Broadcast enabled successfully${NC}"
    else
        echo -e "${RED}✗ Failed to enable broadcast${NC}"
        exit 1
    fi
}

# Function to disable broadcast
disable_broadcast() {
    echo -e "${YELLOW}Disabling broadcast for session $TEST_SESSION_ID...${NC}"
    RESPONSE=$(curl -s -X POST "${API_BASE}/sessions/${TEST_SESSION_ID}/broadcast/disable")
    ENABLED=$(echo "$RESPONSE" | jq -r '.broadcast_enabled')

    if [ "$ENABLED" = "false" ]; then
        echo -e "${GREEN}✓ Broadcast disabled successfully${NC}"
    else
        echo -e "${RED}✗ Failed to disable broadcast${NC}"
        exit 1
    fi
}

# Function to check agents
check_agents() {
    echo -e "${YELLOW}Checking for active agents...${NC}"
    AGENTS=$(curl -s "${API_BASE}/agents")
    AGENT_COUNT=$(echo "$AGENTS" | jq '. | length')

    if [ "$AGENT_COUNT" -eq 0 ]; then
        echo -e "${YELLOW}○ No agents currently active${NC}"
        echo "To start agents: docker compose up -d --scale agent=3"
    else
        echo -e "${GREEN}✓ Found $AGENT_COUNT active agent(s)${NC}"
        echo "$AGENTS" | jq -r '.[] | "  - \(.agent_id): \(.conn_state) (accepted: \(.stats.submits_accepted_total), rejected: \(.stats.submits_rejected_total))"'
    fi
}

# Run tests
echo "========================================="
echo "Running Integration Tests"
echo "========================================="
echo ""

check_backend
echo ""

get_sessions
echo ""

check_broadcast_status
echo ""

enable_broadcast
echo ""

check_broadcast_status
echo ""

check_agents
echo ""

echo "========================================="
echo "Manual Testing Steps"
echo "========================================="
echo ""
echo "1. Start agents (if not already running):"
echo "   docker compose up -d --scale agent=2"
echo ""
echo "2. Monitor agent logs:"
echo "   docker compose logs -f agent"
echo ""
echo "3. Connect a miner to localhost:3333 and submit shares"
echo ""
echo "4. Check agents API:"
echo "   curl ${API_BASE}/agents | jq"
echo ""
echo "5. View UI at http://localhost:3000"
echo "   - Check Sessions list for broadcast toggle"
echo "   - Verify agents are shown with stats"
echo ""
echo "6. Clean up:"
echo "   docker compose down"
echo ""

disable_broadcast
echo ""

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Integration test completed successfully!${NC}"
echo -e "${GREEN}=========================================${NC}"

