# Minecraft Integration Guide

**Complete guide for setting up and using Minecraft with EVOKE Prosperity**

---

## Overview

The EVOKE Minecraft integration allows students to collect awards in EVOKE and automatically receive rewards on a Minecraft server via RCON (Remote Console). This creates a seamless educational gaming experience.

**Features:**
- ✅ Award collection delivers items to Minecraft
- ✅ Tier-based rewards (common → epic → legendary)
- ✅ Visual effects and announcements
- ✅ Online player detection
- ✅ Server health monitoring
- ✅ Works locally for development
- ✅ Compatible with production servers

---

## Architecture

```
EVOKE Backend                 Minecraft Server
┌─────────────────┐          ┌────────────────┐
│ API Endpoints   │          │  Java Edition  │
│  - Award        │          │  - RCON Port   │
│  - Reward       │          │  - Players     │
│  - Status       │          │  - Items       │
└────────┬────────┘          └────────▲───────┘
         │                            │
         └────── RCON Protocol ───────┘
              (TCP Port 25575)
```

### Data Flow: Award Collection

```
1. Student clicks "Collect Award" in EVOKE UI
   └─ Award ID: award-123, Tier: legendary

2. EVOKE backend calls:
   POST /api/minecraft/reward/collect/user-456
   {
     "player_name": "Steve",
     "award_id": "award-123",
     "tier": "legendary"
   }

3. Minecraft Bridge (RCON Client) connects to server
   └─ Server: localhost:25575
   └─ Password: minecraft

4. RCON executes commands:
   ├─ give Steve diamond_block 1
   ├─ give Steve netherite_ingot 2
   ├─ give Steve enchanted_golden_apple 1
   ├─ give Steve emerald 32
   ├─ effect give Steve strength 120 2
   └─ say Steve earned a Legendary Badge! 📙✨

5. Player sees:
   ├─ Items appear in inventory
   ├─ Strength effect applied
   ├─ Server announcement
   └─ Reward complete!
```

---

## Local Setup (Development)

### Prerequisites

```bash
# Required
- Docker & Docker Compose
- Python 3.9+
- PostgreSQL (or Docker)

# Optional but recommended
- Minecraft Java Edition client (to join server)
- A Minecraft account (can play in offline mode)
```

### Step 1: Start Minecraft Server

```bash
# Start local Minecraft server with RCON enabled
docker compose -f docker-compose.minecraft.yml up -d

# Verify server is running
docker logs minecraft-server-dev

# Wait 30-60 seconds for full startup
```

**Expected output:**
```
minecraft | Done (2.345s)! For help, type "help"
minecraft | [Server thread/INFO]: Running Paperclip version git-Paper-...
minecraft | [Server thread/INFO]: RCON running on 0.0.0.0:25575
```

### Step 2: Configure EVOKE

**Update .env file:**
```bash
# Minecraft Configuration
MINECRAFT_SERVER_HOST=localhost
MINECRAFT_SERVER_PORT=25575
MINECRAFT_RCON_PASSWORD=minecraft
MINECRAFT_RCON_TIMEOUT=5.0
```

### Step 3: Enable Minecraft Routes in EVOKE

**In evoke/main.py, add:**
```python
# After app creation
from evoke.minecraft_routes import setup_minecraft_routes

app = FastAPI()
setup_minecraft_routes(app)
```

### Step 4: Restart EVOKE

```bash
# Stop current backend
Ctrl+C

# Start with Minecraft integration
python -m evoke.main
```

**Verify integration:**
```bash
curl http://localhost:8000/api/minecraft/status
# Should return: {"connected": true, "server_host": "localhost", ...}
```

### Step 5: Join Server (Optional)

**To play on the local server:**
1. Launch Minecraft Java Edition
2. Multiplayer → Add Server
3. Server Name: "EVOKE Dev"
4. Server Address: `localhost:25565`
5. Join Server

**You can now play and receive rewards from EVOKE!**

---

## API Endpoints

### POST /api/minecraft/reward/collect/{user_id}

Deliver reward to player on Minecraft server.

**Request:**
```bash
curl -X POST http://localhost:8000/api/minecraft/reward/collect/user-123 \
  -H "Content-Type: application/json" \
  -d '{
    "player_name": "Steve",
    "award_id": "award-456",
    "tier": "legendary",
    "reward_type": "badge"
  }'
```

**Response:**
```json
{
  "status": "success",
  "message": "Reward delivered to Steve",
  "player": "Steve",
  "tier": "legendary",
  "award_id": "award-456"
}
```

**Reward Tiers:**

| Tier | Items | Effect | Message |
|------|-------|--------|---------|
| common | 1x diamond, 5x iron_ingot, 2x emerald | Speed I (30s) | earned a Common Badge! 📕 |
| epic | 5x diamond, 1x diamond_sword, 10x emerald, 1x enchanted_book | Strength I (60s) | earned an Epic Badge! 📘 |
| legendary | 1x diamond_block, 2x netherite_ingot, 1x enchanted_golden_apple, 32x emerald | Strength II (120s) | earned a Legendary Badge! 📙✨ |

### GET /api/minecraft/status

Check Minecraft server connection and online players.

**Request:**
```bash
curl http://localhost:8000/api/minecraft/status
```

**Response:**
```json
{
  "connected": true,
  "server_host": "localhost",
  "server_port": 25575,
  "online_players": ["Steve", "Alex"]
}
```

### GET /api/minecraft/players

Get list of currently online players.

**Request:**
```bash
curl http://localhost:8000/api/minecraft/players
```

**Response:**
```json
{
  "players": ["Steve", "Alex", "Notch"],
  "count": 3
}
```

### POST /api/minecraft/announce

Broadcast message to all players.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/minecraft/announce?message=Welcome%20to%20EVOKE!"
```

**Response:**
```json
{
  "status": "success",
  "message": "Welcome to EVOKE!"
}
```

**Server output:**
```
[Server] Steve: Welcome to EVOKE!
```

### GET /api/minecraft/health

Health check for Minecraft integration.

**Request:**
```bash
curl http://localhost:8000/api/minecraft/health
```

**Response:**
```json
{
  "status": "ok",
  "server_responding": true
}
```

---

## Integration with Award Collection

### Frontend Flow

**1. Student clicks "Collect Award":**
```javascript
// In EVOKE UI
async function collectAward(awardId) {
  const response = await fetch(`/api/awards/${awardId}/collect`, {
    method: 'POST'
  });
  
  const result = await response.json();
  
  if (result.minecraft_delivered) {
    showNotification("Reward delivered to Minecraft!");
  }
}
```

### Backend Integration

**Current implementation (needs update):**

In `evoke/main.py`, modify the award collection endpoint:

```python
@app.post("/api/awards/{award_id}/collect")
async def collect_award(award_id: str, user_id: str):
    # ... existing code ...
    
    # NEW: Deliver to Minecraft
    from evoke.minecraft import get_minecraft_bridge
    
    # Get player's Minecraft username from identity table
    minecraft_username = await db.fetch_one(
        "SELECT minecraft_username FROM evoke_identities WHERE user_id = ?",
        (user_id,)
    )
    
    if minecraft_username:
        bridge = get_minecraft_bridge()
        if not bridge.connected:
            await bridge.connect()
        
        success = await bridge.deliver_reward(
            player_name=minecraft_username,
            reward_type="badge",
            tier=award["tier"],
            award_id=award_id,
        )
        
        return {
            "status": "success",
            "minecraft_delivered": success,
            "message": "Award collected and Minecraft reward delivered!"
        }
```

---

## Production Deployment

### Server Configuration

**Minecraft Server Setup:**

1. Install Minecraft Server (Java Edition)
2. Set RCON in server.properties:
   ```properties
   enable-rcon=true
   rcon.port=25575
   rcon.password=your-secure-password
   ```
3. Restart server
4. Verify RCON works:
   ```bash
   telnet mc.school.local 25575
   ```

### EVOKE Configuration

**Production .env:**
```bash
MINECRAFT_SERVER_HOST=mc.school.local
MINECRAFT_SERVER_PORT=25575
MINECRAFT_RCON_PASSWORD=your-secure-password
MINECRAFT_RCON_TIMEOUT=10.0  # Higher timeout for network delays
```

### Security Considerations

1. **RCON Password**
   - Use strong, random password (32+ characters)
   - Store in secrets manager (not .env on production)
   - Rotate every 90 days

2. **Network**
   - RCON port (25575) should NOT be publicly exposed
   - Only accessible from EVOKE server
   - Use firewall rules to restrict access

3. **Command Validation**
   - Validate player names (alphanumeric only)
   - Sanitize award IDs before sending to RCON
   - Implement rate limiting (max rewards per hour)

4. **Monitoring**
   - Log all RCON commands executed
   - Alert on RCON connection failures
   - Monitor for suspicious commands

---

## Troubleshooting

### "Minecraft server unavailable"

**Diagnosis:**
```bash
# 1. Check if server is running
docker ps | grep minecraft

# 2. Check logs
docker logs minecraft-server-dev

# 3. Try connecting directly
telnet localhost 25575
# Type: minecraft
# Should print response
```

**Solutions:**
```bash
# Restart server
docker restart minecraft-server-dev

# Check RCON password in .env
echo $MINECRAFT_RCON_PASSWORD

# Verify port is exposed
docker port minecraft-server-dev
```

### "Failed to deliver reward"

**Diagnosis:**
```bash
# Check server logs
docker logs minecraft-server-dev | grep -i "give\|error"

# Test manual command
docker exec minecraft-server-dev rcon-cli "say test"
```

**Solutions:**
1. Check player name is online: `/api/minecraft/players`
2. Verify player name spelling (case-sensitive)
3. Restart Minecraft server (corrupted state)
4. Check server disk space

### Reward appears but no items given

**Diagnosis:**
```bash
# Check player inventory is full
docker exec minecraft-server-dev rcon-cli "clear @p"

# Check player permissions
docker exec minecraft-server-dev rcon-cli "op Steve"
```

**Solutions:**
1. Clear some inventory space
2. Make player an op (operator)
3. Check server difficulty (must be >0 for creative mode)

### RCON Connection Timeout

**Diagnosis:**
```bash
# Check if port 25575 is listening
netstat -an | grep 25575

# Check firewall
iptables -L | grep 25575
```

**Solutions:**
1. Increase timeout in .env: `MINECRAFT_RCON_TIMEOUT=15.0`
2. Check server resources (CPU, memory)
3. Restart Minecraft server
4. Check network connectivity

---

## Testing

### Manual Testing

```bash
# 1. Verify server is running
curl http://localhost:8000/api/minecraft/status

# 2. Check online players
curl http://localhost:8000/api/minecraft/players

# 3. Announce message
curl -X POST "http://localhost:8000/api/minecraft/announce?message=EVOKE%20Testing"

# 4. Deliver reward (requires player to be online)
curl -X POST http://localhost:8000/api/minecraft/reward/collect/test-user \
  -H "Content-Type: application/json" \
  -d '{
    "player_name": "Steve",
    "award_id": "test-award-1",
    "tier": "legendary"
  }'
```

### Automated Testing

```bash
# Run tests
pytest tests/test_minecraft_integration.py -v

# Specific test
pytest tests/test_minecraft_integration.py::test_reward_delivery -v
```

### Load Testing

```bash
# Test 50 concurrent reward deliveries
locust -f tests/load_test_minecraft.py \
  --host=http://localhost:8000 \
  --users=50 \
  --spawn-rate=5 \
  --run-time=5m
```

---

## Customization

### Custom Rewards

Edit `evoke/minecraft/minecraft_bridge.py`:

```python
def _get_reward_items(self, tier: str) -> Dict[str, int]:
    rewards = {
        "common": {
            "diamond": 1,
            "emerald": 2,
        },
        "epic": {
            "diamond": 5,
            "netherite_ingot": 1,
        },
        "legendary": {
            "netherite_block": 2,
            "enchanted_golden_apple": 5,
        },
    }
    return rewards.get(tier.lower(), rewards["common"])
```

### Custom Effects

Edit `_get_reward_effect()`:

```python
def _get_reward_effect(self, tier: str) -> Optional[Dict]:
    effects = {
        "legendary": {
            "name": "glowing",      # Change effect
            "duration": 180,        # Change duration (ticks)
            "amplifier": 1,
        },
    }
    return effects.get(tier.lower())
```

### Custom Messages

Edit `_get_reward_message()`:

```python
def _get_reward_message(self, tier: str, award_id: str) -> str:
    messages = {
        "legendary": f"🎉 LEGENDARY ACHIEVEMENT! {award_id}",
    }
    return messages.get(tier.lower())
```

---

## Docker Compose Reference

### Start Server

```bash
docker compose -f docker-compose.minecraft.yml up -d
```

### View Logs

```bash
docker logs -f minecraft-server-dev
```

### Stop Server

```bash
docker compose -f docker-compose.minecraft.yml down
```

### Connect to Console

```bash
docker exec -it minecraft-server-dev rcon-cli
```

### Backup World

```bash
docker exec minecraft-server-dev tar -czf /tmp/world-backup.tar.gz /data
docker cp minecraft-server-dev:/tmp/world-backup.tar.gz ./backups/
```

---

## Production Monitoring

### Prometheus Metrics

Add to `config/prometheus.yml`:

```yaml
- job_name: 'minecraft'
  static_configs:
    - targets: ['minecraft-exporter:9150']
  scrape_interval: 15s
```

### Grafana Dashboard

Import `dashboards/minecraft.json` to see:
- Players online
- TPS (ticks per second)
- Memory usage
- RCON command latency

### Alerts

Add to `config/alerts.yml`:

```yaml
- alert: MinecraftServerDown
  expr: minecraft_server_tps == 0
  for: 2m
  annotations:
    summary: "Minecraft server down"

- alert: HighMinecraftLatency
  expr: minecraft_rcon_latency_ms > 1000
  for: 5m
  annotations:
    summary: "RCON latency > 1 second"
```

---

## References

- [Minecraft RCON Protocol](https://wiki.vg/RCON)
- [Server Properties](https://minecraft.wiki/w/Server.properties)
- [Commands Reference](https://minecraft.wiki/w/Commands)
- [Docker Image (itzg)](https://github.com/itzg/docker-minecraft-server)

---

**Minecraft integration complete! Students can now collect awards in EVOKE and receive rewards in Minecraft.** 🎮
