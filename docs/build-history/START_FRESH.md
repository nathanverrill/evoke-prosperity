# Start Fresh - Complete Setup Guide

**Get EVOKE running from scratch**

---

## Prerequisites Check

```bash
# 1. Verify Python
python3 --version
# Should be 3.9+

# 2. Verify PostgreSQL (if using Docker)
docker --version
docker compose --version

# 3. Verify you're in the right directory
cd ~/evoke-prosperity
pwd
# Should show: /Users/nathanverrill/evoke-prosperity
```

---

## Step 1: Kill Any Old Processes

```bash
# Kill anything on port 8000
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null

# Verify it's gone
lsof -i :8000
# Should show: "lsof: can't open locality database"
```

---

## Step 2: Setup Database

### Option A: Using Docker (Recommended)

```bash
# Terminal 1
cd ~/evoke-prosperity

# Start database
docker compose -f evoke-infra/docker-compose.yml up -d postgres

# Wait for it to start
sleep 5

# Verify it's running
docker ps | grep postgres
# Should see: evoke-postgres container
```

### Option B: Using Local PostgreSQL

```bash
# Make sure PostgreSQL is running on localhost:5432
psql -U postgres -c "SELECT version();"

# Create database if needed
createdb -U postgres evoke
psql -U postgres -d evoke -f evoke-infra/init-db.sql
```

---

## Step 3: Start EVOKE Backend

```bash
# Terminal 2
cd ~/evoke-prosperity

# Clear any Python cache
rm -rf __pycache__ evoke/__pycache__

# Install dependencies (just to be safe)
pip install -r evoke/requirements.txt

# Start the backend
python -m evoke.main
```

**Wait for this output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

---

## Step 4: Access the Website

### Option A: Browser
```bash
# Open in your default browser
open http://localhost:8000

# Or in Terminal 3, use curl to test
curl http://localhost:8000
```

**You should see HTML for the EVOKE website**

### Option B: Test via curl

```bash
# Terminal 3
# Get the homepage
curl http://localhost:8000

# Check health
curl http://localhost:8000/api/health

# Get API docs
curl http://localhost:8000/docs
```

---

## Verify Everything Works

```bash
# Test 1: Homepage loads
curl http://localhost:8000 | head -20
# Should show: <!DOCTYPE html>

# Test 2: API is responding
curl http://localhost:8000/api/health | jq
# Should show: {"status": "ok"}

# Test 3: Missions endpoint
curl http://localhost:8000/api/missions?user_id=test-user-1 | jq

# Test 4: Minecraft (if running)
curl http://localhost:8000/api/minecraft/status | jq
```

---

## Add Optional Services

### Minecraft Server (Local Java)

```bash
# Terminal 3
cd /path/to/minecraft/server
java -Xmx2G -Xms2G -jar server.jar nogui

# Wait for: "Done (X.XXXs)! For help, type "help""
```

Then test Minecraft integration:
```bash
curl http://localhost:8000/api/minecraft/status
```

---

## Access Points

| URL | What You'll See |
|-----|-----------------|
| `http://localhost:8000` | 🏠 EVOKE Homepage |
| `http://localhost:8000/docs` | 📚 Interactive API docs (Swagger) |
| `http://localhost:8000/api/health` | ✅ Health status |
| `http://localhost:8000/api/missions` | 📋 Missions list |
| `http://localhost:8000/api/minecraft/status` | 🎮 Minecraft status |

---

## Troubleshooting

### "Address already in use" error

```bash
# Kill process on 8000
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9

# Or find what's using it
lsof -i :8000
# Then close that application
```

### "Connection refused" for database

```bash
# Check database is running
docker ps | grep postgres

# If not running:
docker compose -f evoke-infra/docker-compose.yml up -d postgres

# Or check local PostgreSQL:
psql -U postgres -c "SELECT 1"
```

### Website shows "404 Not Found"

```bash
# Check static files exist
ls evoke/static/index.html
# Should exist

# Check FastAPI is serving them
curl http://localhost:8000/index.html
# Should return HTML

# If not, restart backend:
# Ctrl+C in Terminal 2
python -m evoke.main
```

### API returns "500 Internal Server Error"

```bash
# Check logs in Terminal 2
# Look for error messages

# Common causes:
# - Database connection failed
# - Missing environment variables
# - Minecraft server not running (but optional)

# Restart backend to see fresh logs:
# Ctrl+C
# python -m evoke.main
```

---

## Full Terminal Setup

```bash
# Terminal 1: Database
cd ~/evoke-prosperity
docker compose -f evoke-infra/docker-compose.yml up -d postgres
docker logs -f postgres

# Terminal 2: Backend
cd ~/evoke-prosperity
python -m evoke.main

# Terminal 3: Testing
cd ~/evoke-prosperity
# Run curl commands or open browser

# Terminal 4: Minecraft (optional)
cd /path/to/minecraft/server
java -Xmx2G -Xms2G -jar server.jar nogui
```

---

## Quick Test Sequence

```bash
# 1. Check backend is up
curl http://localhost:8000/api/health

# 2. Check website loads
curl http://localhost:8000 | grep "DOCTYPE"

# 3. Check missions endpoint
curl http://localhost:8000/api/missions?user_id=test-1

# 4. Check Minecraft integration
curl http://localhost:8000/api/minecraft/status

# If all respond: ✅ Everything is working!
```

---

## Browser Testing

### 1. Open Website
```
http://localhost:8000
```

### 2. Click "Login"
- Dev login will create a test user
- You'll see missions

### 3. Submit Evidence
- Click "Submit" on a mission
- File gets uploaded
- Check terminal for confirmation

### 4. Collect Award (if graded)
- Notifications show awards
- Click "Collect"
- Minecraft reward delivered (if server running)

---

## Environment Variables (Optional)

If you need to customize settings, create/edit `.env`:

```bash
# Database
DATABASE_URL=postgresql://evoke:devsecret123@localhost:5432/evoke

# Minecraft
MINECRAFT_SERVER_HOST=localhost
MINECRAFT_SERVER_PORT=25575
MINECRAFT_RCON_PASSWORD=minecraft

# Brightspace (optional, uses simulator by default)
BRIGHTSPACE_SIMULATOR_MODE=true
```

---

## Next Steps

✅ **Website loading?**
→ Read `PLAY_AND_TEST_GUIDE.md` for testing

✅ **Want to test Minecraft rewards?**
→ Read `MINECRAFT_LOCAL_SETUP.md` or `docker-compose.minecraft.yml`

✅ **Want to modify website?**
→ Edit `evoke/static/index.html`, refresh browser

✅ **Want to test APIs?**
→ Open `http://localhost:8000/docs` (Swagger UI)

---

## Summary

```
1. Kill old processes on 8000
2. Start database (Docker or local)
3. Start backend: python -m evoke.main
4. Open: http://localhost:8000
5. Done! 🎉
```

**If you get stuck, check the logs in Terminal 2 where you started the backend.**
