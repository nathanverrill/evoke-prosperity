#!/bin/bash
#
# Minecraft Integration Setup Script
# Quick start for local Minecraft server with EVOKE integration
#
# Usage:
#   bash scripts/minecraft-setup.sh
#

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ$NC $1"
}

print_success() {
    echo -e "${GREEN}✓$NC $1"
}

print_error() {
    echo -e "${RED}✗$NC $1"
}

# ============================================================================
# Step 1: Check Prerequisites
# ============================================================================
print_header "Checking Prerequisites"

if ! command -v docker &> /dev/null; then
    print_error "Docker not found. Please install Docker."
    exit 1
fi
print_success "Docker installed"

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose not found. Please install Docker Compose."
    exit 1
fi
print_success "Docker Compose installed"

if [ ! -f "docker-compose.minecraft.yml" ]; then
    print_error "docker-compose.minecraft.yml not found. Are you in the project root?"
    exit 1
fi
print_success "docker-compose.minecraft.yml found"

if [ ! -f ".env" ]; then
    print_info "Creating .env file with Minecraft defaults..."
    cat > .env << 'EOF'
# Minecraft Configuration
MINECRAFT_SERVER_HOST=localhost
MINECRAFT_SERVER_PORT=25575
MINECRAFT_RCON_PASSWORD=minecraft
MINECRAFT_RCON_TIMEOUT=5.0
EOF
    print_success ".env created"
else
    print_info "Using existing .env file"
fi

# ============================================================================
# Step 2: Start Minecraft Server
# ============================================================================
print_header "Starting Minecraft Server"

print_info "Pulling latest Minecraft server image..."
docker compose -f docker-compose.minecraft.yml pull

print_info "Starting Minecraft server (this may take a few minutes)..."
docker compose -f docker-compose.minecraft.yml up -d

# Wait for server to be ready
print_info "Waiting for server to start (60 seconds)..."
for i in {1..60}; do
    if docker logs minecraft-server-dev 2>/dev/null | grep -q "Done"; then
        print_success "Minecraft server started successfully"
        break
    fi
    echo -n "."
    sleep 1
done

# ============================================================================
# Step 3: Verify RCON Connection
# ============================================================================
print_header "Verifying RCON Connection"

print_info "Testing RCON connection..."

# Try to connect with a simple command
if docker exec minecraft-server-dev rcon-cli "list" > /dev/null 2>&1; then
    print_success "RCON connection successful"
else
    print_error "RCON connection failed"
    print_info "Server may still be starting. Check logs with: docker logs minecraft-server-dev"
fi

# ============================================================================
# Step 4: Display Server Info
# ============================================================================
print_header "Server Information"

echo "Game Server:"
echo "  Host: localhost"
echo "  Port: 25565"
echo "  Mode: Survival"
echo ""
echo "RCON (for EVOKE integration):"
echo "  Host: localhost"
echo "  Port: 25575"
echo "  Password: minecraft"
echo ""
echo "Data Persistence:"
echo "  Volume: minecraft-data"
echo "  Location: $(docker volume inspect minecraft-data | grep Mountpoint | cut -d'"' -f4)"

# ============================================================================
# Step 5: Verify EVOKE Configuration
# ============================================================================
print_header "Verifying EVOKE Configuration"

echo "Required environment variables:"
echo "  MINECRAFT_SERVER_HOST=${MINECRAFT_SERVER_HOST:-localhost}"
echo "  MINECRAFT_SERVER_PORT=${MINECRAFT_SERVER_PORT:-25575}"
echo "  MINECRAFT_RCON_PASSWORD=${MINECRAFT_RCON_PASSWORD:-minecraft}"
echo ""

if [ -z "$MINECRAFT_SERVER_HOST" ]; then
    print_error "MINECRAFT_SERVER_HOST not set in .env"
else
    print_success "MINECRAFT_SERVER_HOST configured"
fi

# ============================================================================
# Step 6: Test Endpoints
# ============================================================================
print_header "Testing Integration (if EVOKE backend running)"

print_info "Waiting 5 seconds before testing endpoints..."
sleep 5

if command -v curl &> /dev/null; then
    print_info "Testing /api/minecraft/status endpoint..."
    if curl -s http://localhost:8000/api/minecraft/status 2>/dev/null | grep -q "connected"; then
        print_success "Minecraft status endpoint working"
    else
        print_info "Backend not running yet. Start with: python -m evoke.main"
    fi
else
    print_info "curl not found. Skip endpoint tests."
fi

# ============================================================================
# Step 7: Next Steps
# ============================================================================
print_header "Setup Complete!"

echo ""
echo "Next steps:"
echo ""
echo "1. Start EVOKE backend (in another terminal):"
echo "   ${BLUE}python -m evoke.main${NC}"
echo ""
echo "2. Verify Minecraft integration:"
echo "   ${BLUE}curl http://localhost:8000/api/minecraft/status${NC}"
echo ""
echo "3. To connect game client (optional):"
echo "   - Minecraft Java Edition → Multiplayer → Add Server"
echo "   - Name: EVOKE Dev"
echo "   - Address: localhost:25565"
echo ""
echo "4. View server logs:"
echo "   ${BLUE}docker logs -f minecraft-server-dev${NC}"
echo ""
echo "5. Connect to console (run commands):"
echo "   ${BLUE}docker exec -it minecraft-server-dev rcon-cli${NC}"
echo ""
echo "6. Test reward delivery:"
echo "   ${BLUE}curl -X POST http://localhost:8000/api/minecraft/reward/collect/test-user \\${NC}"
echo "   ${BLUE}  -H 'Content-Type: application/json' \\${NC}"
echo "   ${BLUE}  -d '{\"player_name\":\"Steve\",\"award_id\":\"test-1\",\"tier\":\"legendary\"}'${NC}"
echo ""
echo "Documentation:"
echo "   See ${BLUE}MINECRAFT_INTEGRATION.md${NC} for full guide"
echo ""

# ============================================================================
# Cleanup Function
# ============================================================================
cleanup_on_exit() {
    print_info "Cleanup function registered"
    print_info "To stop Minecraft: docker compose -f docker-compose.minecraft.yml down"
    print_info "To remove data: docker volume rm minecraft-data"
}

trap cleanup_on_exit EXIT

print_success "Minecraft setup complete!"
