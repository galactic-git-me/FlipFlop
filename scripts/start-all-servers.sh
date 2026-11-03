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
VERBOSE=false

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
        EBAY_ENVIRONMENT=sandbox EBAY_LISTING_ENVIRONMENT=sandbox python run_dev.py --host 0.0.0.0 --port 4314 > /tmp/flipflop-backend.log 2>&1 &
    elif [ "$name" = "admin" ]; then
        NODE_ENV=development NEXT_PUBLIC_API_URL=http://localhost:4314 NEXT_PUBLIC_FLIPFLOP_ENV=development npm run dev -- -p 4312 -H 0.0.0.0 > /tmp/flipflop-admin.log 2>&1 &
    elif [ "$name" = "frontend" ]; then
        NODE_ENV=development BACKEND_URL=http://localhost:4314 NEXT_PUBLIC_API_URL=http://localhost:4314 NEXT_PUBLIC_FLIPFLOP_ENV=development npm run dev -- --webpack -p 4313 -H 0.0.0.0 > /tmp/flipflop-frontend.log 2>&1 &
    fi

    local pid=$!
    echo -e "${color}✅ $name started (PID: $pid)${NC}"
    echo "$pid" >> "$PID_FILE"
}

# Retire only tracked processes still identifying this checkout.
PID_FILE="/tmp/flipflop-servers-$(id -u).pids"
if [ -f "$PID_FILE" ]; then
    while IFS= read -r old_pid; do
        [[ "$old_pid" =~ ^[0-9]+$ ]] || continue
        old_command=$(ps -p "$old_pid" -o args= 2>/dev/null || true)
        if [[ "$old_command" == *"$PROJECT_ROOT"* ]]; then
            pkill -TERM -P "$old_pid" 2>/dev/null || true
            kill -TERM "$old_pid" 2>/dev/null || true
        fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
fi
: > "$PID_FILE"

echo "Starting servers..."
echo ""

# Start servers
if [ "$NO_BACKEND" = false ]; then
    start_server "backend" "$PROJECT_ROOT/flipflop-api" "python" "run_dev.py" "4314" "$YELLOW" || true
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
echo -e "${YELLOW}  Backend:  http://localhost:4314${NC}"
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

# Wait for interrupt while preserving server process ownership.
trap 'while read -r child; do [[ "$child" =~ ^[0-9]+$ ]] && kill "$child" 2>/dev/null || true; done < "$PID_FILE"; rm -f "$PID_FILE"; exit 0' INT TERM
while true; do sleep 3600; done
