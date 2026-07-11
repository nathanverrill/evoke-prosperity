# EVOKE Prosperity MVP - Quick Reference

## 🚀 Start Everything

```bash
cd /Users/nathanverrill/evoke-prosperity
./quick-start.sh
```

**What it does:**
1. Starts infrastructure (postgres, redpanda, opensearch, minio, openwebui, minecraft)
2. Seeds database (campaigns, missions, quests, users)
3. Starts application (fastapi, brightspace-sim, minecraft-bridge)
4. Reports access points and health

**Time to ready:** ~2 minutes

## 🌐 Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| **Operations Hub** | http://localhost:8000 | Main learner UI - submit missions, collect awards, chat |
| **Companion Mode** | http://localhost:8000/companion.html | Sidebar for Minecraft - quick access while playing |
| **Teacher Review** | http://localhost:8001/teacher-review | Grade submissions (simulated Brightspace) |
| **OpenWebUI** | http://localhost:3000 | Configure B1llbot AI mentor |
| **Redpanda Console** | http://localhost:8080 | View event stream |
| **OpenSearch Dash** | http://localhost:5601 | View search indexes/timelines |
| **MinIO Console** | http://localhost:9001 | View evidence files |

## ⚡ Test the Flow (2 min)

1. **Login:** http://localhost:8000 → "Auto-Login"
2. **Submit:** Upload any file to Mission 1 → Get common-tier award
3. **Grade:** http://localhost:8001/teacher-review → Grade as "Epic"
4. **Collect:** Back to /api/notifications → Click "Collect"
5. **Result:** `RewardCollected` event published → Minecraft Bridge delivers reward

## 📡 API Endpoints

### Learner Workflow
```bash
# Login
POST /api/dev-login

# Get missions
GET /api/missions?user_id={id}

# Submit evidence (file upload)
POST /api/submit-evidence
  user_id, mission_id, file

# Get notifications & awards
GET /api/notifications/{user_id}
GET /api/awards/{user_id}

# Collect award (triggers Minecraft delivery)
POST /api/awards/{award_id}/collect
```

### Minecraft
```bash
# Link Minecraft account
POST /api/minecraft/link
  user_id, minecraft_username

# Get/submit quests
GET /api/mc-quests
POST /api/mc-quests/{quest_id}/submit
  user_id, observation_text, screenshot (file)
```

### AI
```bash
# Chat with B1llbot
POST /api/billbot/chat
  user_id, message
```

### Internal
```bash
# Teacher review webhook (called by brightspace-sim)
POST /api/webhooks/brightspace/review
  user_id, mission_id, rating
```

## 🛠 Troubleshooting

| Issue | Fix |
|-------|-----|
| Postgres won't start | `docker compose logs postgres` |
| Database not seeded | `cd evoke-infra && python seed.py` |
| FastAPI won't start | `docker compose logs web` |
| Minecraft reward not delivered | Player must be online OR bridge queues for next login |
| AI not working | Check `AI_ENABLED=true` in .env, verify OpenWebUI running |
| Authorization errors | Check browser console, ensure CORS is allowed |

## 📊 Database

**Test User Credentials:**
- Learner: learner@evoke.local (pre-seeded)
- Minecraft: DemoLearner (pre-linked)

**12 Missions:**
1. Follow the Flow (Explore)
2. Money Moves (Explore)
3. Building Blocks (Imagine)
4. Pitch Perfect (Imagine)
5. Risk and Reward (Act)
6. Market Makers (Act)
7. Community Capital (Communicate)
8. Digital Economy (Communicate)
9. Sustainable Growth (Act)
10. Global Markets (Act)
11. Craft Your Pitch (Communicate)
12. Worth Backing (Communicate)

**Award Tiers:**
- common → stone/dirt
- epic → diamond/haste effect
- legendary → netherite pickaxe/golden apple

## 🎯 Key Design Decisions

1. **Awards collected, not granted**
   - `collected_at` is NULL until learner clicks "Collect"
   - Minecraft delivery ONLY on collection (not award)

2. **Minecraft optional for learner, required for platform**
   - No grade depends on Minecraft per docs/canon/thread5.md
   - But reward delivery is built-in infrastructure feature

3. **Event-driven architecture**
   - All domain activity flows through Redpanda
   - AI worker, Minecraft bridge, LMS sync are independent consumers

4. **Campaign as data, not code**
   - 12 missions are rows in missions table
   - 4 badges (superpowers) are rows in badges table
   - New 6-week curriculum = new rows, not code changes

5. **One server per organization**
   - All services (app, infra, Minecraft) on one machine
   - Deployed as git repo + docker compose + .env
   - Perfect for K-12 schools (no managed services needed)

## 🔧 Configuration

**Edit .env to change:**
```bash
# Infrastructure (passwords, ports)
INFRA_SECRET=devsecret123
PORT_EVOKE=8000

# Features
AI_ENABLED=true

# LMS (change when implementing real Brightspace)
BRIGHTSPACE_SIM_URL=http://brightspace-sim:8001

# Minecraft rewards (edit init-db.sql, then reseed)
```

## 📚 Documentation

- **SETUP.md** - Detailed setup & troubleshooting
- **ARCHITECTURE.md** - System design & rationale
- **CONCEPTS.md** - Glossary & orientation
- **BUILD_PROMPT.md** - MVP spec (what was built)
- **BUILD_SUMMARY.md** - What's implemented vs. planned

## 🚢 Production Readiness

**For production, swap:**
- `brightspace-sim` → Real Brightspace (LTI + Award Service API)
- Dev auto-login → Real LMS identity
- Wireframe UI → Polish from ui/ mockup
- Username Minecraft linking → UUID-based

**Already production-ready:**
- Event architecture (Redpanda, workers)
- Database schema (Postgres)
- Storage (MinIO → real S3)
- RCON client (Minecraft delivery)
- API surface (no breaking changes expected)

## 💡 Tips

- **Companion Mode:** Designed for 600px-wide window next to Minecraft
- **B1llbot:** Configure prompts in OpenWebUI admin panel
- **Quests:** Side quests are optional, mission quests pair 1:1 with missions
- **Offline:** Minecraft bridge checks every 60s for offline players, delivers when they log in
- **Events:** View live event stream in Redpanda Console (http://localhost:8080)

---

**Built with:** FastAPI + Postgres + Redpanda + Minecraft + OpenWebUI

**Status:** ✅ Fully functional MVP ready for demo & testing
