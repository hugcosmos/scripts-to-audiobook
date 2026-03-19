#!/bin/bash
# Docker Entrypoint Script for Scripts to Audiobook

set -e

# Color definitions
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Scripts to Audiobook - Docker       ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Ensure directories exist
mkdir -p data/outputs data/outputs_test logs

# Check if .env file exists, create empty one if not
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating empty .env file...${NC}"
    touch .env
fi

# Function to check if a port is available
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 1
    fi
    return 0
}

# Function to wait for a service to be ready
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=1

    echo -e "${YELLOW}Waiting for $name to be ready...${NC}"
    while [ $attempt -le $max_attempts ]; do
        if curl -sf "$url" >/dev/null 2>&1; then
            echo -e "${GREEN}✓ $name is ready!${NC}"
            return 0
        fi
        echo -e "  Attempt $attempt/$max_attempts..."
        sleep 1
        attempt=$((attempt + 1))
    done
    echo -e "${RED}✗ $name failed to start${NC}"
    return 1
}

# Start backend (background)
echo -e "${GREEN}Starting backend service (Port 8000)...${NC}"
python3 backend/main.py &
BACKEND_PID=$!

# Wait for backend to be ready
if ! wait_for_service "http://localhost:8000/api/health" "Backend"; then
    echo -e "${RED}Backend failed to start. Check logs for details.${NC}"
    exit 1
fi

# Start frontend (background)
echo -e "${GREEN}Starting frontend service (Port 5000)...${NC}"
cd frontend && NODE_ENV=production PORT=5000 node dist/index.cjs &
FRONTEND_PID=$!

# Wait a moment for frontend to start
sleep 2

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Services are running!               ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "  - Backend API: ${GREEN}http://localhost:8000${NC}"
echo -e "  - Frontend App: ${GREEN}http://localhost:5000${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Handle shutdown gracefully
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"
    kill $FRONTEND_PID 2>/dev/null || true
    kill $BACKEND_PID 2>/dev/null || true
    wait
    echo -e "${GREEN}✓ All services stopped${NC}"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Wait for processes
wait $FRONTEND_PID $BACKEND_PID
