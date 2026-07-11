# ⚡ EVOKE + Minecraft: 5-Minute Quick Start

**Get up and running in 5 minutes**

---

## Terminal 1: Start Minecraft

```bash
cd ~/evoke-prosperity
bash scripts/minecraft-setup.sh

# Wait for: "Minecraft setup complete!" ✓
```

---

## Terminal 2: Start EVOKE Backend

```bash
cd ~/evoke-prosperity
python -m evoke.main

# Wait for: "Uvicorn running on http://0.0.0.0:8000" ✓
```

---

## Terminal 3: Test It! 🚀

### Test 1: Check Status
```bash
curl http://localhost:8000/api/minecraft/status
# Should return: {"connected": true, ...}
```

### Test 2: Deliver a Reward
```bash
curl -X POST http://localhost:8000/api/minecraft/reward/collect/user-1 \
  -H "Content-Type: application/json" \
  -d '{
    "player_name": "Steve",
    "award_id": "award-1",
    "tier": "legendary"
  }'

# Should return: {"status": "success", "message": "Reward delivered to Steve"}
```

### Test 3: Send Announcement
```bash
curl -X POST "http://localhost:8000/api/minecraft/announce?message=EVOKE%20is%20live!"

# Should return: {"status": "success"}
```

### Test 4: List Players
```bash
curl http://localhost:8000/api/minecraft/players
# Should return: {"players": [], "count": 0}
```

---

## Optional: Play in Minecraft

1. Open **Minecraft Java Edition**
2. **Multiplayer** → **Add Server**
   - Name: `EVOKE Dev`
   - Address: `localhost:25565`
3. **Join Server**
4. Run this in Terminal 3:

```bash
curl -X POST http://localhost:8000/api/minecraft/reward/collect/user-1 \
  -H "Content-Type: application/json" \
  -d '{"player_name":"Steve","award_id":"legendary-1","tier":"legendary"}'
```

5. Check your inventory! 🎉
   - Diamond Block
   - Netherite Ingots
   - Enchanted Golden Apple
   - Emeralds

---

## Reward Tiers

| Tier | Command | Items |
|------|---------|-------|
| **Common** | `"tier": "common"` | 1 diamond, 5 iron, 2 emeralds + Speed I |
| **Epic** | `"tier": "epic"` | 5 diamonds, sword, book + Strength I |
| **Legendary** | `"tier": "legendary"` | Diamond block, netherite, golden apple + Strength II |

---

## Troubleshooting

**Minecraft won't start?**
```bash
docker logs minecraft-server-dev | tail -20
docker restart minecraft-server-dev
```

**Connection refused?**
```bash
# Check EVOKE is running
curl http://localhost:8000/api/health

# Check Minecraft is running
curl http://localhost:8000/api/minecraft/status
```

**No items in inventory?**
```bash
# Make sure you used exact player name (case-sensitive!)
# Make sure inventory isn't full
# Try "common" tier first (smaller rewards)
```

---

## Key APIs

| Endpoint | Purpose | Example |
|----------|---------|---------|
| `GET /api/minecraft/status` | Check connection | `curl http://localhost:8000/api/minecraft/status` |
| `GET /api/minecraft/players` | List online players | `curl http://localhost:8000/api/minecraft/players` |
| `POST /api/minecraft/reward/collect/{id}` | Deliver reward | See above |
| `POST /api/minecraft/announce` | Broadcast message | `curl -X POST "http://localhost:8000/api/minecraft/announce?message=Hello"` |
| `GET /api/minecraft/health` | Health check | `curl http://localhost:8000/api/minecraft/health` |

---

## File Reference

| File | Purpose |
|------|---------|
| `PLAY_AND_TEST_GUIDE.md` | Full testing guide with scenarios |
| `MINECRAFT_INTEGRATION.md` | Complete technical documentation |
| `docker-compose.minecraft.yml` | Docker Minecraft server config |
| `evoke/minecraft/` | Minecraft bridge source code |

---

## Next Steps

✅ **Working locally?** → Read `PLAY_AND_TEST_GUIDE.md` for advanced testing  
✅ **Want to deploy?** → Read `OPERATIONS.md` for production setup  
✅ **Need more info?** → Read `MINECRAFT_INTEGRATION.md` for full docs  

---

**Everything working? You've successfully integrated Minecraft with EVOKE! 🎮✨**
