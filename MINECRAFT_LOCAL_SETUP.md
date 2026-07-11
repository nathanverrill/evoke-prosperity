# Local Minecraft Server Setup (No Docker)

**Run Minecraft server directly on your machine using Java**

---

## Prerequisites

You've already done this:
- ✅ Java installed (JDK 17+)
- ✅ Minecraft server jar downloaded

Now let's configure it for EVOKE.

---

## Step 1: Enable RCON

Edit your `server.properties` file:

```bash
# Find your server folder and edit server.properties
# (Usually in the directory where you run the server)

nano server.properties
# or use your preferred editor
```

**Find or add these lines:**

```properties
# RCON Configuration
enable-rcon=true
rcon.port=25575
rcon.password=minecraft

# (Optional but recommended)
# Server settings
difficulty=1
gamemode=0
pvp=false
online-mode=false
max-players=20
```

**Save and close** (Ctrl+X, Y, Enter in nano)

---

## Step 2: Start Minecraft Server

```bash
# Navigate to your server folder
cd /path/to/minecraft/server

# Start server
java -Xmx2G -Xms2G -jar server.jar nogui

# Wait for: "Done (2.345s)! For help, type "help""
# This means server is ready!
```

**Troubleshooting:**
```bash
# If you get "the system cannot find the file specified"
# Make sure you're in the right directory containing server.jar

# If you get "EULA not accepted"
# Edit eula.txt and change eula=false to eula=true
```

---

## Step 3: Verify RCON Works

**While server is running, open another terminal:**

```bash
# Test RCON connection
# You need an RCON client tool

# Option A: Use mcrcon (if installed)
mcrcon -h localhost -p 25575 -P minecraft "list"
# Should respond: "There are X of max Y players online"

# Option B: Use telnet (manual test)
telnet localhost 25575
# Type: minecraft
# You should see a response

# Option C: Use Python (from EVOKE)
python3 << 'EOF'
import socket
import struct

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('localhost', 25575))
print("Connected to RCON!")
sock.close()
EOF
```

---

## Step 4: Configure EVOKE

**Update .env file in EVOKE project:**

```bash
cd ~/evoke-prosperity

# Edit .env
nano .env
```

**Add/update these lines:**

```bash
# Minecraft Configuration
MINECRAFT_SERVER_HOST=localhost
MINECRAFT_SERVER_PORT=25575
MINECRAFT_RCON_PASSWORD=minecraft
MINECRAFT_RCON_TIMEOUT=5.0
```

**Save the file**

---

## Step 5: Start EVOKE Backend

```bash
cd ~/evoke-prosperity

# Start PostgreSQL (if needed)
docker compose -f evoke-infra/docker-compose.yml up -d postgres
sleep 5

# Start EVOKE
python -m evoke.main

# Wait for: "Uvicorn running on http://0.0.0.0:8000"
```

---

## Step 6: Test the Integration

**In a new terminal:**

```bash
# Check connection
curl http://localhost:8000/api/minecraft/status

# Expected response:
# {"connected": true, "server_host": "localhost", "server_port": 25575, ...}

# Deliver a reward
curl -X POST http://localhost:8000/api/minecraft/reward/collect/user-1 \
  -H "Content-Type: application/json" \
  -d '{
    "player_name": "Steve",
    "award_id": "award-1",
    "tier": "legendary"
  }'

# Expected response:
# {"status": "success", "message": "Reward delivered to Steve", ...}
```

---

## Terminal Setup (Recommended)

**Open 3 terminals side by side:**

### Terminal 1: Minecraft Server
```bash
cd /path/to/minecraft/server
java -Xmx2G -Xms2G -jar server.jar nogui

# Keep this running!
# You'll see commands executed here
```

### Terminal 2: EVOKE Backend
```bash
cd ~/evoke-prosperity
python -m evoke.main

# Keep this running!
# You'll see API calls here
```

### Terminal 3: Testing
```bash
# Use this for testing commands
curl http://localhost:8000/api/minecraft/status
curl -X POST http://localhost:8000/api/minecraft/reward/collect/...
```

---

## Verify Everything Works

**In Terminal 3, run these tests:**

```bash
# Test 1: Check server status
curl http://localhost:8000/api/minecraft/status | jq

# Expected:
{
  "connected": true,
  "server_host": "localhost",
  "server_port": 25575,
  "online_players": []
}

# Test 2: List online players
curl http://localhost:8000/api/minecraft/players

# Test 3: Announce message
curl -X POST "http://localhost:8000/api/minecraft/announce?message=EVOKE%20is%20live!"

# Check Terminal 1 - you should see:
# [Server] EVOKE is live!

# Test 4: Deliver common reward
curl -X POST http://localhost:8000/api/minecraft/reward/collect/user-1 \
  -H "Content-Type: application/json" \
  -d '{"player_name":"Steve","award_id":"common-1","tier":"common"}'

# Check Terminal 1 - you should see commands:
# [Server] give Steve diamond 1
# [Server] give Steve iron_ingot 5
# [Server] effect give Steve speed 30 1
```

---

## Play in Minecraft Client

### Option 1: Single Player (if server is on same machine)

1. Open Minecraft Java Edition
2. Single Player → Create World
3. Open to LAN
4. Note the port number
5. Join from another Minecraft client at: `localhost:PORT`

### Option 2: Multiplayer (if server is on different machine)

1. Open Minecraft Java Edition
2. Multiplayer → Add Server
3. Name: `EVOKE Dev`
4. Address: `YOUR_SERVER_IP:25565`
5. Join!

### When You Deliver Rewards

```bash
# While playing, run:
curl -X POST http://localhost:8000/api/minecraft/reward/collect/test-1 \
  -H "Content-Type: application/json" \
  -d '{"player_name":"Steve","award_id":"legendary-1","tier":"legendary"}'

# You'll see in game:
# ✓ Items appear in inventory
# ✓ Strength effect (particles)
# ✓ Server announcement: "Steve earned a Legendary Badge! 📙✨"
```

---

## Monitoring the Server

### Watch Console Output

**Terminal 1 (where server runs):**
```
[Server] give Steve diamond 1
[Server] effect give Steve strength 120 2
[Server] say Steve earned a Legendary Badge! 📙✨
[Server thread/INFO]: Steve joined the game
[Server thread/INFO]: Steve left the game
```

### Check EVOKE Logs

**Terminal 2 (where EVOKE runs):**
```
INFO:     POST /api/minecraft/reward/collect/user-1 HTTP/1.1" 200
INFO:     Reward delivered to Steve: legendary badge
```

---

## Troubleshooting

### Issue: Connection refused

**Solution:**
```bash
# 1. Check Minecraft server is running
# (should see "Done" message in Terminal 1)

# 2. Verify RCON is enabled in server.properties
grep "enable-rcon" server.properties
# Should show: enable-rcon=true

# 3. Verify port is correct
grep "rcon.port" server.properties
# Should show: rcon.port=25575

# 4. Restart server
# Stop (Ctrl+C in Terminal 1)
# Start again (same command)
```

### Issue: Authentication failed

**Solution:**
```bash
# 1. Check RCON password matches
# In server.properties:
grep "rcon.password" server.properties
# Should show: rcon.password=minecraft

# 2. Check EVOKE .env matches
cat .env | grep MINECRAFT_RCON_PASSWORD
# Should show: MINECRAFT_RCON_PASSWORD=minecraft

# 3. Restart EVOKE
# Stop (Ctrl+C in Terminal 2)
# Start again (same command)
```

### Issue: Reward delivered but no items appear

**Solution:**
```bash
# 1. Make sure you're in survival mode (not creative)
# Type in Minecraft chat: /gamemode survival

# 2. Clear inventory if full
# Type in Minecraft chat: /clear @s

# 3. Try again:
curl -X POST http://localhost:8000/api/minecraft/reward/collect/test-1 \
  -H "Content-Type: application/json" \
  -d '{"player_name":"Steve","award_id":"test-1","tier":"common"}'
```

### Issue: Server keeps stopping

**Solution:**
```bash
# Increase memory allocation
java -Xmx4G -Xms4G -jar server.jar nogui
#      ^4GB  ^4GB (increase if you have it)

# Or check logs for crashes
# Look at Terminal 1 output for errors
```

---

## Server Commands You Can Use

**Type these in the Minecraft server console (Terminal 1):**

```bash
# Check online players
list

# Give item to player
give Steve diamond 1

# Apply potion effect
effect give Steve speed 30 1

# Broadcast message
say Server maintenance in 5 minutes

# Stop server gracefully
stop
```

---

## Stopping the Server

**In Terminal 1:**
```bash
# Type this command in the server console:
stop

# Or press Ctrl+C
# (though "stop" command is cleaner)
```

---

## Performance Tips

### Memory Management
```bash
# Small server (2-4 players)
java -Xmx2G -Xms2G -jar server.jar nogui

# Medium server (4-10 players)
java -Xmx4G -Xms4G -jar server.jar nogui

# Large server (10+ players)
java -Xmx8G -Xms8G -jar server.jar nogui
```

### Network Optimization
```properties
# In server.properties, add:
network-compression-threshold=256
max-tick-time=60000
```

### View Distance
```properties
# In server.properties:
view-distance=10    # Default is fine for local testing
```

---

## Complete Setup Checklist

- [ ] Java installed: `java -version`
- [ ] Server jar downloaded
- [ ] server.properties configured (RCON enabled)
- [ ] server.properties has correct RCON password
- [ ] EVOKE .env has matching RCON password
- [ ] Minecraft server started: `java -Xmx2G -Xms2G -jar server.jar nogui`
- [ ] EVOKE backend started: `python -m evoke.main`
- [ ] Test status: `curl http://localhost:8000/api/minecraft/status`
- [ ] Test reward: `curl -X POST http://localhost:8000/api/minecraft/reward/collect/...`

---

## Testing Commands Quick Reference

```bash
# Status check
curl http://localhost:8000/api/minecraft/status

# List players
curl http://localhost:8000/api/minecraft/players

# Announce message
curl -X POST "http://localhost:8000/api/minecraft/announce?message=Hello"

# Common reward
curl -X POST http://localhost:8000/api/minecraft/reward/collect/user-1 \
  -H "Content-Type: application/json" \
  -d '{"player_name":"Steve","award_id":"common-1","tier":"common"}'

# Epic reward
curl -X POST http://localhost:8000/api/minecraft/reward/collect/user-2 \
  -H "Content-Type: application/json" \
  -d '{"player_name":"Steve","award_id":"epic-1","tier":"epic"}'

# Legendary reward
curl -X POST http://localhost:8000/api/minecraft/reward/collect/user-3 \
  -H "Content-Type: application/json" \
  -d '{"player_name":"Steve","award_id":"legendary-1","tier":"legendary"}'

# Health check
curl http://localhost:8000/api/minecraft/health
```

---

## Next Steps

✅ **Minecraft server running?**  
→ Proceed to testing commands above

✅ **EVOKE backend running?**  
→ Test integration with curl commands

✅ **Rewards working?**  
→ Join Minecraft and see items appear!

✅ **Need more testing?**  
→ See `PLAY_AND_TEST_GUIDE.md`

---

**You're all set! Enjoy testing EVOKE + Minecraft integration locally.** 🎮✨
