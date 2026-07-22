#!/bin/bash
set -e

echo "🚀 EVOKE Prosperity MVP - Quick Start"
echo "======================================"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker."
    exit 1
fi

# Copy env file
if [ ! -f .env ]; then
    echo "📋 Creating .env from template..."
    cp .env.example .env
fi

# Start infrastructure. The AI stack (ollama/CUDA, open-webui, litellm,
# presidio) and the Minecraft server are opt-in compose profiles -- they're
# multi-GB pulls that have filled contributor disks. Enable them with
# EVOKE_PROFILES=ai,minecraft in the root .env. Without them the core stack
# runs fine (B1llBot uses canned replies; Minecraft features stay dormant).
EVOKE_PROFILES=$(grep -E '^EVOKE_PROFILES=' .env 2>/dev/null | cut -d= -f2)
echo ""
if [ -n "$EVOKE_PROFILES" ]; then
    echo "🟦 Starting infrastructure (core + profiles: $EVOKE_PROFILES)..."
else
    echo "🟦 Starting core infrastructure (postgres, redpanda, opensearch, minio)..."
    echo "   (AI + Minecraft stacks are opt-in: set EVOKE_PROFILES=ai,minecraft in .env)"
fi
cd evoke-infra
# --build: the minecraft image is built locally; a plain `up` after pulling
# new commits keeps running the stale image.
if [ -n "$EVOKE_PROFILES" ]; then
    COMPOSE_PROFILES="$EVOKE_PROFILES" docker compose up -d --build
else
    docker compose up -d --build
fi
echo "⏳ Waiting for services to be healthy..."
sleep 30

# Check postgres health
echo "🔍 Checking Postgres..."
until docker compose exec -T postgres pg_isready -U evoke >/dev/null 2>&1; do
    echo "  Waiting for Postgres..."
    sleep 5
done
echo "✓ Postgres is ready"

# Seed database
echo ""
echo "🌱 Seeding database with missions, quests, and test users..."
python3 seed.py || {
    echo "⚠️  Seed script failed. Make sure Postgres is healthy."
    exit 1
}

# Start application services
echo ""
echo "🟢 Starting application services (fastapi, brightspace-sim, minecraft-bridge)..."
cd ../evoke
# Docker Compose only auto-loads a .env file from the same directory as the
# compose file it's running -- the root .env (MINECRAFT_PUBLIC_HOST,
# PUBLIC_WEB_URL, etc.) was silently never reaching this stack without this,
# no matter how it was set at the root. Kept in sync on every run so editing
# the root .env is still the one place to change things.
cp ../.env .env
# --build matters here: pulling a commit that adds Python deps (reportlab,
# qrcode, bcrypt, ...) with a plain `up -d` reuses the old image and the
# web container crash-loops on ModuleNotFoundError. Layer caching makes
# this a no-op when requirements.txt hasn't changed.
docker compose up -d --build

echo "⏳ Waiting for services to start..."
sleep 15

# Check health
echo ""
echo "🔍 Checking service health..."
curl -s http://localhost:8000/health | grep -q "ok" && echo "✓ FastAPI: OK" || echo "⚠️  FastAPI: check logs"
curl -s http://localhost:8001/health | grep -q "ok" && echo "✓ Brightspace Sim: OK" || echo "⚠️  Brightspace Sim: check logs"

# Optional ngrok tunnel for remote access (opt-in via ENABLE_NGROK=true in
# .env -- off by default, since it exposes this instance, including the
# unprotected /api/admin/* routes, to the public internet). Requires the
# ngrok CLI to already be installed and authenticated (`ngrok config add-authtoken`).
# NGROK_STATIC_DOMAIN (optional): a free reserved domain from your ngrok
# account -- when set, the tunnel URL stays constant across restarts instead
# of getting a new random one each time, so PUBLIC_WEB_URL never goes stale.
ENABLE_NGROK=$(grep -E '^ENABLE_NGROK=' ../.env 2>/dev/null | cut -d= -f2)
NGROK_STATIC_DOMAIN=$(grep -E '^NGROK_STATIC_DOMAIN=' ../.env 2>/dev/null | cut -d= -f2)
NGROK_URL=""
if [ "$ENABLE_NGROK" = "true" ]; then
    if ! command -v ngrok &> /dev/null; then
        echo "⚠️  ENABLE_NGROK=true but ngrok isn't installed -- skipping tunnel."
    else
        echo ""
        pkill -f "ngrok http 8000" 2>/dev/null || true
        sleep 1
        if [ -n "$NGROK_STATIC_DOMAIN" ]; then
            echo "🌐 Starting ngrok tunnel on reserved domain $NGROK_STATIC_DOMAIN..."
            nohup ngrok http 8000 --domain="$NGROK_STATIC_DOMAIN" --log=stdout > /tmp/evoke-ngrok.log 2>&1 &
        else
            echo "🌐 Starting ngrok tunnel for remote access..."
            nohup ngrok http 8000 --log=stdout > /tmp/evoke-ngrok.log 2>&1 &
        fi
        disown
        for i in $(seq 1 15); do
            NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null \
                | python3 -c "import sys,json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null)
            [ -n "$NGROK_URL" ] && break
            sleep 1
        done
        if [ -n "$NGROK_URL" ]; then
            echo "✓ ngrok tunnel: $NGROK_URL"
            if grep -q '^PUBLIC_WEB_URL=' ../.env; then
                sed -i '' "s#^PUBLIC_WEB_URL=.*#PUBLIC_WEB_URL=$NGROK_URL#" ../.env
            else
                echo "PUBLIC_WEB_URL=$NGROK_URL" >> ../.env
            fi
            cp ../.env .env
            docker compose up -d web
            sleep 3
        else
            echo "⚠️  ngrok didn't report a tunnel URL in time -- check /tmp/evoke-ngrok.log"
        fi
    fi
fi

echo ""
echo "✅ EVOKE Prosperity MVP is running!"
echo ""
echo "📚 Access points:"
echo "  • Operations Hub (Main UI):    http://localhost:8000"
echo "  • Companion Mode (Sidebar):    http://localhost:8000/companion.html"
echo "  • Teacher Review:              http://localhost:8001/teacher-review"
echo "  • OpenWebUI (B1llbot config):  http://localhost:3000"
echo "  • Redpanda Console:            http://localhost:8080"
echo "  • OpenSearch Dashboards:       http://localhost:5601"
echo "  • MinIO Console:               http://localhost:9001"
if [ -n "$NGROK_URL" ]; then
    echo "  • Remote access (ngrok):       $NGROK_URL"
fi
echo ""
echo "🎯 Quick test:"
echo "  1. Open http://localhost:8000 in browser"
echo "  2. Click 'Auto-Login'"
echo "  3. Upload a file to any mission"
echo "  4. Go to /teacher-review to grade it"
echo "  5. Click 'Collect' on the award → triggers Minecraft delivery"
echo ""
echo "📖 For detailed setup & troubleshooting, see SETUP.md"
