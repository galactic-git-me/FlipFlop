#!/bin/bash
set -e

echo "🚀 FlipFlop Docker Deployment Script"
echo "===================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Docker
echo "📦 Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker found${NC}"

# Check Docker Compose
echo "📦 Checking Docker Compose installation..."
if ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found. Please install Docker Compose.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker Compose found${NC}"

# Build images
echo ""
echo "🏗️  Building Docker images..."
docker compose build

# Start services
echo ""
echo "🚀 Starting services..."
docker compose up -d

# Wait for services to be healthy
echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check PostgreSQL
echo ""
echo "🔍 Checking PostgreSQL..."
if docker compose exec -T postgres pg_isready -U flipper -d flipflop > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PostgreSQL is ready${NC}"
else
    echo -e "${YELLOW}⚠️  PostgreSQL still starting...${NC}"
fi

# Check API
echo ""
echo "🔍 Checking API..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API is healthy${NC}"
else
    echo -e "${YELLOW}⚠️  API still starting...${NC}"
fi

# Display URLs
echo ""
echo "===================================="
echo -e "${GREEN}🎉 FlipFlop is Starting!${NC}"
echo "===================================="
echo ""
echo "Services will be available at:"
echo -e "  ${YELLOW}Storefront:${NC}  http://localhost:3000"
echo -e "  ${YELLOW}Admin:${NC}        http://localhost:3001"
echo -e "  ${YELLOW}API:${NC}          http://localhost:8000"
echo -e "  ${YELLOW}Database:${NC}     localhost:5432"
echo ""
echo "Credentials:"
echo -e "  ${YELLOW}DB User:${NC}      flipper"
echo -e "  ${YELLOW}DB Password:${NC}  flipper_secure_password_123"
echo ""
echo "Monitor logs with:"
echo "  docker compose logs -f"
echo ""
echo "Stop services with:"
echo "  docker compose down"
echo ""
echo -e "${GREEN}Please wait 30-60 seconds for all services to fully start.${NC}"
