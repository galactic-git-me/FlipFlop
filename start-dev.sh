#!/bin/bash
set -e

echo "🚀 FlipFlop Development Environment Setup"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker.${NC}"
    exit 1
fi

# Stop existing dev containers
echo "🛑 Stopping existing dev containers..."
docker compose -f docker-compose.dev.yml down 2>/dev/null || true

# Build dev images
echo ""
echo "🏗️  Building development images..."
docker compose -f docker-compose.dev.yml build

# Start services
echo ""
echo "🚀 Starting development services..."
docker compose -f docker-compose.dev.yml up -d

# Wait for services
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check health
echo ""
echo "🔍 Checking service status..."
docker compose -f docker-compose.dev.yml ps

# Display info
echo ""
echo "=========================================="
echo -e "${GREEN}✅ Development Environment Ready!${NC}"
echo "=========================================="
echo ""
echo -e "${BLUE}Services:${NC}"
echo -e "  ${YELLOW}Storefront:${NC}  http://andromeda-ts:13000  (or http://localhost:13000)"
echo -e "  ${YELLOW}Admin:${NC}        http://andromeda-ts:13001  (or http://localhost:13001)"
echo -e "  ${YELLOW}API:${NC}          http://andromeda-ts:18000  (or http://localhost:18000)"
echo -e "  ${YELLOW}Database:${NC}     localhost:15432"
echo -e "  ${YELLOW}Redis:${NC}        localhost:16379"
echo ""
echo -e "${BLUE}Database Credentials:${NC}"
echo -e "  ${YELLOW}User:${NC}     flipper"
echo -e "  ${YELLOW}Password:${NC} flipper_secure_password_123"
echo ""
echo -e "${BLUE}Auto-Reload:${NC}"
echo "  ✓ Backend (FastAPI) reloads on file changes"
echo "  ✓ Storefront (Next.js) hot-reloads on file changes"
echo "  ✓ Admin (Next.js) hot-reloads on file changes"
echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo ""
echo "  ${YELLOW}View logs:${NC}"
echo "    docker compose -f docker-compose.dev.yml logs -f"
echo ""
echo "  ${YELLOW}View logs for specific service:${NC}"
echo "    docker compose -f docker-compose.dev.yml logs -f api"
echo "    docker compose -f docker-compose.dev.yml logs -f storefront"
echo "    docker compose -f docker-compose.dev.yml logs -f admin"
echo ""
echo "  ${YELLOW}Restart a service:${NC}"
echo "    docker compose -f docker-compose.dev.yml restart api"
echo ""
echo "  ${YELLOW}Stop all services:${NC}"
echo "    docker compose -f docker-compose.dev.yml down"
echo ""
echo "  ${YELLOW}Stop and remove volumes:${NC}"
echo "    docker compose -f docker-compose.dev.yml down -v"
echo ""
echo "  ${YELLOW}Access database:${NC}"
echo "    docker compose -f docker-compose.dev.yml exec postgres psql -U flipper -d flipflop"
echo ""
echo "  ${YELLOW}Access Redis:${NC}"
echo "    docker compose -f docker-compose.dev.yml exec redis redis-cli"
echo ""
echo -e "${GREEN}Happy coding! 🎉${NC}"
