#!/bin/bash
# FlipFlop Platform - Start All Servers (Bash version)

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🚀 FlipFlop Platform - Starting all servers"
echo "Project root: $PROJECT_ROOT"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Parse arguments
NO_BACKEND=false
NO_ADMIN=false
NO_FRONTEND=false
VERBOSE=falseáÁZZZZ \8

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-backend) NO_BACKEND=true; shift ;;
        --no-admin) NO_ADMIN=true; shift ;;
        --no-frontend) NO_FRONTEND=true; shift ;;
        -v|--verbose) VERBOSE=true; shift ;;
        *) shift ;;
    esac
done

# Function to start a server
start_server() {
    local name=$1
    local path=$2
    local command=$3
    local args=$4
    local port=$5
    local color=$6

    if [ ! -d "$path" ]; then
        echo -e "${RED}❌ Path not found: $path${NC}"
        return 1
    fi

    echo -e "${color}Starting $name...${NC}"
    echo -e "${CYAN}  Path: $path${NC}"
    echo -e "${CYAN}  Port: $port${NC}"

    if [ "$VERBOSE" = true ]; then
        echo -e "${CYAN}  Command: $command $args${NC}"
    fi

    cd "$path"

    # Start the server in background
    if [ "$name" = "backend" ]; then
        python run_dev.py --host 0.0.0.0 --port 4311 > /tmp/flipflop-backend.log 2>&1 &
    elif [ "$name" = "admin" ]; then
        NEXT_PUBLIC_API_URL=http://localhost:4311 npm run dev -- -p 4312 -H 0.0.0.0 > /tmp/flipflop-admin.log 2>&1 &
    elif [ "$name" = "frontend" ]; then
        BACKEND_URL=http://localhost:4311 NEXT_PUBLIC_API_URL=http://localhost:4311 npm run dev -- -p 4313 -H 0.0.0.0 > /tmp/flipflop-frontend.log 2>&1 &
    fi

    local pid=$!
    echo -e "${color}✅ $name started (PID: $pid)${NC}"
    echo "$pid" >> /tmp/flipflop-servers.pids
}

# Clean up previous PIDs file
rm -f /tmp/flipflop-servers.pids

echo "Starting servers..."
echo ""

# Start servers
if [ "$NO_BACKEND" = false ]; then
    start_server "backend" "$PROJECT_ROOT/flipflop-api" "python" "run_dev.py" "4311" "$YELLOW" || true
fi

if [ "$NO_ADMIN" = false ]; then
    start_server "admin" "$PROJECT_ROOT/flipflop-admin" "npm" "run dev" "4312" "$GREEN" || true
fi

if [ "$NO_FRONTEND" = false ]; then
    start_server "frontend" "$PROJECT_ROOT/../FlipFlop.shop" "npm" "run dev" "4313" "$MAGENTA" || true
fi

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}Servers Running${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo ""
echo -e "${CYAN}🔗 Access URLs:${NC}"
echo -e "${YELLOW}  Backend:  http://localhost:4311${NC}"
echo -e "${GREEN}  Admin:    http://localhost:4312${NC}"
echo -e "${MAGENTA}  Frontend: http://localhost:4313${NC}"
echo ""
echo -e "${CYAN}Log files:${NC}"
echo -e "${YELLOW}  /tmp/flipflop-backend.log${NC}"
echo -e "${GREEN}  /tmp/flipflop-admin.log${NC}"
echo -e "${MAGENTA}  /tmp/flipflop-frontend.log${NC}"
echo ""
echo -e "${CYAN}Press Ctrl+C to stop all servers${NC}"
echo ""

# Wait for interrupt
trap 'kill $(cat /tmp/flipflop-servers.pids 2>/dev/null); rm -f /tmp/flipflop-servers.pids; echo "Servers stopped"; exit 0' INT

if [ -f /tmp/flipflop-servers.pids ]; then
    wait $(cat /tmp/flipflop-servers.pids | head -1)
fi
