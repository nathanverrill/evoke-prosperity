# EVOKE + Minecraft: Play & Test Guide

**Complete walkthrough for testing the integration locally**

---

## Prerequisites

```bash
# Required
- Docker & Docker Compose
- Python 3.9+
- PostgreSQL (or Docker)
- curl or Postman (for API testing)
- Git (already have it)

# Optional but recommended
- Minecraft Java Edition (to see rewards in game)
- jq (JSON parsing for curl responses)
```

**Check what you have:**
```bash
docker --version
docker-compose --version
python3 --version
curl --version
```

---

## Quick Start (5 minutes)

### Step 1: Start All Services

**Terminal 1 - Start Minecraft:**
```bash
cd ~/evoke-prosperity
bash scripts/minecraft-setup.sh

# Wait for: "Minecraft server started successfully" ✓
```

**Terminal 2 - Start Database (if not running):**
```bash
docker compose -f evoke-infra/docker-compose.yml up -d postgres
sleep 5
echo "Database started"
```

**Terminal 3 - Start EVOKE Backend:**
```bash
cd ~/evoke-prosperity
python -m evoke.main

# Wait for: "Uvicorn running on http://0.0.0.0:8000" ✓
```

### Step 2: Verify Everything is Running

```bash
# Check Minecraft status
curl http://localhost:8000/api/minecraft/status

# Expected response:
# {"connected": true, "server_host": "localhost", "server_port": 25575, "online_players": []}

# Check EVOKE health
curl http://localhost:8000/api/health

# Expected response:
# {"status": "ok"}
```

### Step 3: Deliver Your First Reward

```bash
curl -X POST http://localhost:8000/api/minecraft/reward/collect/test-user-1 \
  -H "Content-Type: application/json" \
  -d '{
    "player_name": "Steve",
    "award_id": "award-123",
    "tier": "legendary"
  }'

# Expected response:
# {"status": "success", "message": "Reward delivered to Steve", ...}
```

**That's it! You've delivered a reward.** 🎉

---

## Detailed Testing Scenarios

### Scenario 1: Test Without Minecraft Client (API Only)

**Best for:** Quick testing, CI/CD, headless testing

#### 1a. Check Server Status
```bash
# Get server info
curl http://localhost:8000/api/minecraft/status | jq

# Expected output:
{
  "connected": true,
  "server_host": "localhost",
  "server_port": 25575,
  "online_players": []
}
```

#### 1b. List Online Players
```bash
curl http://localhost:8000/api/minecraft/players | jq

# Expected output:
{
  "players": [],
  "count": 0
}
# (empty because no one is logged in yet)
```

#### 1c. Announce Message to Server
```bash
curl -X POST "http://localhost:8000/api/minecraft/announce?message=Testing%20EVOKE%20Integration!"

# Expected output:
{
  "status": "success",
  "message": "Testing EVOKE Integration!"
}

# Check server logs:
docker logs minecraft-server-dev | grep "Testing EVOKE"
```

#### 1d. Deliver Common Tier Reward
```bash
curl -X POST http://localhost:8000/api/minecraft/reward/collect/user-001 \
  -H "Content-Type: application/json" \
  -d '{
    "player_name": "TestPlayer",
    "award_id": "award-001",
    "tier": "common",
    "reward_type": "badge"
  }' | jq

# Expected output:
{
  "status": "success",
  "message": "Reward delivered to TestPlayer",
  "player": "TestPlayer",
  "tier": "common",
  "award_id": "award-001"
}

# Check server logs for commands executed:
docker logs minecraft-server-dev | grep "give TestPlayer"
```

#### 1e. Deliver Epic Tier Reward
```bash
curl -X POST http://localhost:8000/api/minecraft/reward/collect/user-002 \
  -H "Content-Type: application/json" \
  -d '{
    "player_name": "TestPlayer",
    "award_id": "award-002",
    "tier": "epic",
    "reward_type": "badge"
  }' | jq
```

#### 1f. Deliver Legendary Tier Reward
```bash
curl -X POST http://localhost:8000/api/minecraft/reward/collect/user-003 \
  -H "Content-Type: application/json" \
  -d '{
    "player_name": "TestPlayer",
    "award_id": "award-003",
    "tier": "legendary",
    "reward_type": "badge"
  }' | jq

# Check what items were given:
docker logs minecraft-server-dev | grep "give TestPlayer"
# Should see: diamond_block, netherite_ingot, enchanted_golden_apple, emerald
```

#### 1g. Health Check
```bash
curl http://localhost:8000/api/minecraft/health | jq

# Expected:
{
  "status": "ok",
  "server_responding": true
}
```

---

### Scenario 2: Test With Minecraft Client

**Best for:** Visual verification, full experience testing

#### Setup: Join the Server

1. **Open Minecraft Java Edition**
2. **Multiplayer → Add Server**
   - Name: `EVOKE Dev`
   - Address: `localhost:25565`
3. **Join Server**
4. Wait for world to load (may take 30 seconds)

#### Test: Receive Rewards in Game

**Terminal (while in game):**
```bash
# Deliver reward to your player
curl -X POST http://localhost:8000/api/minecraft/reward/collect/user-123 \
  -H "Content-Type: application/json" \
  -d '{
    "player_name": "Steve",
    "award_id": "award-legendary-1",
    "tier": "legendary"
  }'
```

**What you should see in game:**
1. ✅ Items appear in inventory (check inventory screen)
2. ✅ Strength effect applied (green particles around player)
3. ✅ Server announcement in chat: "Steve earned a Legendary Badge! 📙✨"
4. ✅ Items in inventory:
   - 1x Diamond Block
   - 2x Netherite Ingot
   - 1x Enchanted Golden Apple
   - 32x Emerald

#### Test: Server Announcements

**While in game, run:**
```bash
curl -X POST "http://localhost:8000/api/minecraft/announce?message=Welcome%20to%20EVOKE!%20%F0%9F%8E%AE"
```

**In game:** You'll see chat message: `[Server] Welcome to EVOKE! 🎮`

#### Test: Check Online Players

```bash
curl http://localhost:8000/api/minecraft/players | jq

# Expected (while you're in game):
{
  "players": ["Steve"],
  "count": 1
}
```

---

## Complete End-to-End Flow Test

**Simulates the full EVOKE → Minecraft journey**

### Step 1: Simulate LTI Launch (Mock)

In real usage, this comes from Brightspace. For testing, we'll use mock data:

```bash
# Simulate student logging in via LTI
# In real system: Student clicks "Launch EVOKE" in Brightspace
# For now, we'll just simulate the user ID

export USER_ID="student-123"
export PLAYER_NAME="Steve"
echo "Simulating LTI launch for $USER_ID"
```

### Step 2: Mock Evidence Submission

```bash
# In real system: Student submits evidence in EVOKE
# This would call POST /api/submit-evidence
# For testing, we'll just verify the database

docker exec -it evoke-postgres psql -U evoke -d evoke -c \
  "INSERT INTO submissions (id, user_id, mission_id, evidence_url, created_at) 
   VALUES ('sub-001', 'student-123', 'mission-001', 'https://example.com/evidence.jpg', NOW())
   ON CONFLICT DO NOTHING;"

echo "Evidence submission recorded"
```

### Step 3: Mock Teacher Grading

```bash
# In real system: Teacher grades in Brightspace
# Webhook syncs grade back
# For testing, we'll simulate the grade webhook

curl -X POST http://localhost:8000/api/webhooks/brightspace/grade \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "submission_id=sub-001&brightspace_user_id=6001&grade=95&feedback=Excellent work!" | jq

# Expected response:
# {"status": "success", "message": "Grade 95 processed, legendary tier award granted", ...}
```

### Step 4: Collect Award in EVOKE

```bash
# In real system: Student clicks "Collect Award"
# This would call POST /api/awards/{id}/collect
# Which calls Minecraft reward delivery

curl -X POST http://localhost:8000/api/minecraft/reward/collect/$USER_ID \
  -H "Content-Type: application/json" \
  -d "{
    \"player_name\": \"$PLAYER_NAME\",
    \"award_id\": \"award-legendary-1\",
    \"tier\": \"legendary\",
    \"reward_type\": \"badge\"
  }" | jq
```

### Step 5: Verify in Minecraft

**If playing in game:**
- Check inventory (should have diamond block, netherite, etc.)
- See server announcement
- See strength effect

**Via API:**
```bash
# Check online players
curl http://localhost:8000/api/minecraft/players | jq

# Check server health
curl http://localhost:8000/api/minecraft/health | jq
```

---

## Reward Tiers Reference

### Common Tier
```bash
curl -X POST http://localhost:8000/api/minecraft/reward/collect/test-1 \
  -H "Content-Type: application/json" \
  -d '{"player_name": "Steve", "award_id": "common-1", "tier": "common"}'

# Items given:
# - 1x diamond
# - 5x iron_ingot
# - 2x emerald
# Effect: Speed I (30 seconds)
# Message: "earned a Common Badge! 📕"
```

### Epic Tier
```bash
curl -X POST http://localhost:8000/api/minecraft/reward/collect/test-2 \
  -H "Content-Type: application/json" \
  -d '{"player_name": "Steve", "award_id": "epic-1", "tier": "epic"}'

# Items given:
# - 5x diamond
# - 1x diamond_sword
# - 10x emerald
# - 1x enchanted_book
# Effect: Strength I (60 seconds)
# Message: "earned an Epic Badge! 📘"
```

### Legendary Tier
```bash
curl -X POST http://localhost:8000/api/minecraft/reward/collect/test-3 \
  -H "Content-Type: application/json" \
  -d '{"player_name": "Steve", "award_id": "legendary-1", "tier": "legendary"}'

# Items given:
# - 1x diamond_block
# - 2x netherite_ingot
# - 1x enchanted_golden_apple
# - 32x emerald
# Effect: Strength II (120 seconds)
# Message: "earned a Legendary Badge! 📙✨"
```

---

## Troubleshooting

### Issue: "Minecraft server unavailable"

**Diagnosis:**
```bash
# Check if Minecraft container is running
docker ps | grep minecraft
# Should see: minecraft-server-dev

# Check logs
docker logs minecraft-server-dev | tail -20

# Try connecting with RCON
docker exec minecraft-server-dev rcon-cli "list"
# Should show: "There are X players online"
```

**Solutions:**
```bash
# Restart Minecraft
docker restart minecraft-server-dev

# Wait 60 seconds
sleep 60

# Verify again
curl http://localhost:8000/api/minecraft/status
```

### Issue: "No online players" when I'm in game

**Solutions:**
```bash
# Player name must match exactly (case-sensitive!)
# If your Minecraft name is "Steve", use "Steve" not "steve"

# Give reward to your exact player name
curl -X POST http://localhost:8000/api/minecraft/reward/collect/test \
  -H "Content-Type: application/json" \
  -d '{"player_name": "YourExactMinecraftName", "award_id": "test-1", "tier": "common"}'

# Check who's online
curl http://localhost:8000/api/minecraft/players | jq .players
```

### Issue: Reward delivered but items don't appear

**Solutions:**
```bash
# 1. Make sure you're playing in survival mode (not creative)
# 2. Make sure your inventory isn't full
# 3. Clear some inventory space

# Via server console:
docker exec minecraft-server-dev rcon-cli "clear @p"

# 4. Try again
curl -X POST http://localhost:8000/api/minecraft/reward/collect/test \
  -H "Content-Type: application/json" \
  -d '{"player_name": "Steve", "award_id": "test-1", "tier": "common"}'
```

### Issue: Server won't start

**Solutions:**
```bash
# Check Docker is running
docker ps

# Pull latest image
docker compose -f docker-compose.minecraft.yml pull

# Remove old container
docker compose -f docker-compose.minecraft.yml down

# Start fresh
docker compose -f docker-compose.minecraft.yml up -d

# Wait and check logs
sleep 30
docker logs minecraft-server-dev | grep "Done"
```

---

## Performance Testing

### Test 1: Rapid Fire Rewards

```bash
# Deliver 10 rewards rapidly
for i in {1..10}; do
  curl -X POST http://localhost:8000/api/minecraft/reward/collect/test-$i \
    -H "Content-Type: application/json" \
    -d "{\"player_name\": \"Steve\", \"award_id\": \"award-$i\", \"tier\": \"common\"}" \
    -w "Response time: %{time_total}s\n" \
    -o /dev/null -s
done

# All should complete quickly (<500ms each)
```

### Test 2: Concurrent Rewards

```bash
# Install parallel tool (if not have)
# brew install parallel  (Mac)
# sudo apt install parallel  (Linux)

# Send 20 concurrent reward requests
seq 1 20 | parallel -j 20 \
  'curl -X POST http://localhost:8000/api/minecraft/reward/collect/test-{} \
    -H "Content-Type: application/json" \
    -d "{\"player_name\": \"Steve\", \"award_id\": \"award-{}\", \"tier\": \"epic\"}" \
    -o /dev/null -s'

# All should succeed without errors
```

### Test 3: Load Testing

```bash
# Using Locust (if installed)
locust -f tests/load_test_minecraft.py \
  --host=http://localhost:8000 \
  --users=50 \
  --spawn-rate=5 \
  --run-time=5m
```

---

## Automated Testing

```bash
# Run all integration tests
pytest tests/test_integration_e2e.py -v

# Run Minecraft-specific tests (if created)
pytest tests/test_minecraft_integration.py -v

# Run manual happy path
bash tests/manual_test_happy_path.sh
```

---

## Monitor Everything

### In Another Terminal: Watch Minecraft Logs

```bash
docker logs -f minecraft-server-dev | grep -E "give|say|effect"

# You'll see RCON commands in real-time:
# [Server] give Steve diamond 1
# [Server] effect give Steve strength 120 2
# [Server] say Steve earned a Common Badge!
```

### Watch Backend Logs

```bash
# Terminal running evoke
# You'll see: INFO - /api/minecraft/reward/collect called
# Response: {"status": "success", ...}
```

### Monitor Metrics

```bash
# Check Prometheus (if configured)
curl http://localhost:9090/api/v1/query?query=minecraft_rewards_delivered
```

---

## Advanced: Customize Rewards

Edit `evoke/minecraft/minecraft_bridge.py`:

### Change Items Given

```python
def _get_reward_items(self, tier: str) -> Dict[str, int]:
    rewards = {
        "common": {
            "diamond": 10,  # Change from 1 to 10
            "emerald": 5,   # Change from 2 to 5
        },
        # ... rest of tiers
    }
```

Then restart:
```bash
# Ctrl+C in EVOKE terminal
python -m evoke.main
```

### Change Effects

```python
def _get_reward_effect(self, tier: str) -> Optional[Dict]:
    effects = {
        "legendary": {
            "name": "glowing",  # Change from strength
            "duration": 300,
            "amplifier": 0,
        },
    }
```

### Change Messages

```python
def _get_reward_message(self, tier: str, award_id: str) -> str:
    messages = {
        "legendary": f"🎉 ULTIMATE! You earned {award_id}!",
    }
```

---

## Summary of Commands

**Startup:**
```bash
bash scripts/minecraft-setup.sh    # Terminal 1
python -m evoke.main               # Terminal 2
```

**Test (API):**
```bash
curl http://localhost:8000/api/minecraft/status
curl http://localhost:8000/api/minecraft/players
curl -X POST http://localhost:8000/api/minecraft/announce?message=Hello
curl -X POST http://localhost:8000/api/minecraft/reward/collect/test-1 ...
```

**Test (Game):**
1. Join `localhost:25565` in Minecraft
2. Run curl command
3. See items appear in inventory!

---

## Next: Integration with EVOKE Awards

To fully integrate with EVOKE award collection:

**In evoke/main.py, modify the award collection endpoint:**

```python
@app.post("/api/awards/{award_id}/collect")
async def collect_award(award_id: str, user_id: str):
    # ... existing code ...
    
    # NEW: Get player's Minecraft username
    minecraft_username = await db.fetch_one(
        "SELECT minecraft_username FROM evoke_identities WHERE user_id = ?",
        (user_id,)
    )
    
    # Deliver to Minecraft
    if minecraft_username:
        bridge = get_minecraft_bridge()
        if not bridge.connected:
            await bridge.connect()
        
        await bridge.deliver_reward(
            player_name=minecraft_username,
            reward_type="badge",
            tier=award["tier"],
            award_id=award_id,
        )
```

---

**That's it! You now have a complete testing guide for EVOKE + Minecraft.** 🎮✨

Start with Scenario 1 (API testing), then move to Scenario 2 (game client) for the full experience!
