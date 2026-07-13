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

# Start infrastructure
echo ""
echo "🟦 Starting infrastructure (postgres, redpanda, opensearch, minio, minecraft)..."
cd evoke-infra
docker compose up -d
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
docker compose up -d

echo "⏳ Waiting for services to start..."
sleep 15

# Check health
echo ""
echo "🔍 Checking service health..."
curl -s http://localhost:8000/health | grep -q "ok" && echo "✓ FastAPI: OK" || echo "⚠️  FastAPI: check logs"
curl -s http://localhost:8001/health | grep -q "ok" && echo "✓ Brightspace Sim: OK" || echo "⚠️  Brightspace Sim: check logs"

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
echo ""
echo "🎯 Quick test:"
echo "  1. Open http://localhost:8000 in browser"
echo "  2. Click 'Auto-Login'"
echo "  3. Upload a file to any mission"
echo "  4. Go to /teacher-review to grade it"
echo "  5. Click 'Collect' on the award → triggers Minecraft delivery"
echo ""
echo "📖 For detailed setup & troubleshooting, see SETUP.md"
