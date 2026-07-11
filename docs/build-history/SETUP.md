# EVOKE Prosperity MVP - Setup & Run Guide

## Overview

EVOKE Prosperity is a mission-based learning platform for financial literacy and entrepreneurship education. This MVP demonstrates:

- 12-mission curriculum with Brightspace integration
- Award pipeline: submission → AI review → teacher review → collection
- Minecraft reward delivery via RCON
- B1llbot AI mentor integration
- Two UIs: Operations Hub (main) and Companion Mode (narrow sidebar for Minecraft)

## Architecture Components

1. **PostgreSQL** - System of record (campaigns, users, missions, awards, Minecraft links)
2. **Redpanda** - Event bus (EvidenceSubmitted, AwardGranted, RewardCollected, etc.)
3. **OpenSearch** - Read models (timelines, dashboards)
4. **MinIO** - Evidence file storage
5. **FastAPI App** - Main backend API
6. **Brightspace Simulator** - Fake LMS for demo (real Brightspace integration ready)
7. **Minecraft Server** - Paper/Vanilla with RCON enabled
8. **Minecraft Reward Bridge** - Consumes events, delivers rewards via RCON
9. **OpenWebUI** - AI gateway (B1llbot custom model configuration)

## Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for seed script)
- ~4GB RAM available
- Ports: 5432, 8000, 8001, 9000, 9001, 9092, 8080, 5601, 3000, 25565, 25575

## Quick Start

### 1. Clone and Setup

```bash
cd /Users/nathanverrill/evoke-prosperity
cp .env.example .env
```

### 2. Start Infrastructure

```bash
cd evoke-infra
docker compose up -d
```

This brings up:
- PostgreSQL (schema auto-initialized)
- Redpanda (Kafka)
- OpenSearch
- MinIO
- OpenWebUI
- Minecraft Server

Wait for all services to be healthy (~30s):

```bash
docker compose ps
```

### 3. Initialize Database

```bash
cd evoke-infra
# Make sure postgres is running
python seed.py
```

This creates:
- `evoke-prosperity` campaign
- Demo school organization
- Test users (learner@evoke.local / teacher@evoke.local)
- 12 missions (Follow the Flow → Worth Backing)
- 16 Minecraft quests (12 mission quests + 4 side quests)
- Minecraft reward catalog (common/epic/legendary tier)
- Dev learner linked to Minecraft username "DemoLearner"

### 4. Start Application Services

```bash
cd evoke
docker compose up -d
```

This starts:
- FastAPI app (port 8000) - /api/* endpoints + static UIs
- Brightspace Simulator (port 8001) - /teacher-review UI
- Minecraft Reward Bridge - listens to Redpanda events

### 5. Verify All Services

```bash
# All should respond with 200 OK
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8000/api/health/database
curl http://localhost:8000/api/health/minio
curl http://localhost:8000/api/health/opensearch
```

## Using the System

### Main Operations Hub UI

**URL:** http://localhost:8000/

1. Click "Auto-Login" to sign in as the demo learner
2. **Missions** tab shows the 12 curriculum missions - click "Submit Evidence" to upload a file
3. **Notifications** tab shows pending awards that need to be collected
4. Click "Collect Reward" - this triggers `RewardCollected` event → Minecraft delivery
5. **Minecraft** section: link your account (or use "DemoLearner" for demo)
6. **B1llbot** chat: ask questions, get in-character responses

### Companion Mode (Narrow Sidebar)

**URL:** http://localhost:8000/companion.html

Designed to sit open next to Minecraft while playing:
- Shows current mission
- Pending awards with quick collect button
- B1llbot chat (same replies as main site)

### Teacher Review (Brightspace Simulator)

**URL:** http://localhost:8001/teacher-review

1. Appears when you submit evidence
2. Shows pending submissions per assignment
3. Grade as "Epic" or "Legendary"
4. Awards appear in the learner's notifications

## Acceptance Scenario (MVP Demo)

This is the flow you can test end-to-end:

1. **Login** → Auto-login as demo learner
2. **Submit Evidence** → Upload any file to Mission 1
   - `EvidenceSubmitted` event triggers
   - Common-tier award granted immediately
   - AI review runs (if AI_ENABLED=true) → Epic award
3. **Teacher Review** → Go to /teacher-review UI
   - Grade the submission Epic or Legendary
   - Webhook calls `/api/webhooks/brightspace/review`
   - Award granted, notification appears
4. **Link Minecraft** → Use username "DemoLearner" (pre-linked)
5. **Collect Awards** → Click "Collect" in notifications
   - `RewardCollected` event published
   - Minecraft Reward Bridge consumes it
   - RCON command delivers item/effect in-game (if Minecraft is running)
6. **Chat B1llbot** → Ask "Who are you?" or "Tell me about Keel"
   - Calls OpenWebUI billbot model
   - Returns in-character response

## API Surface

### Core Endpoints

```
POST   /api/dev-login                      Auto-login (dev only)
POST   /api/login                          Email + password login (local auth)
GET    /api/missions?user_id={id}          List missions for campaign
POST   /api/submit-evidence                Submit evidence file
POST   /api/webhooks/brightspace/review    Webhook from Brightspace (teacher grade)

GET    /api/notifications/{user_id}        Unread + read notifications
GET    /api/awards/{user_id}               All awards for learner
POST   /api/awards/{award_id}/collect      Collect award → trigger Minecraft delivery

POST   /api/minecraft/link                 Link user to Minecraft username
GET    /api/minecraft/link/{user_id}       Get Minecraft link status
GET    /api/mc-quests                      List Minecraft quests (mission + side)
POST   /api/mc-quests/{quest_id}/submit    Submit quest evidence (observation + screenshot)

POST   /api/billbot/chat                   Chat with B1llbot AI mentor
```

### Health Checks

```
GET    /health                             App health
GET    /api/health/database                Database connectivity
GET    /api/health/minio                   MinIO/S3 connectivity
GET    /api/health/opensearch              OpenSearch connectivity
```

## Event Flow

```
User submits evidence
  ↓ EvidenceSubmitted event
  ↓ [Workers consume]
  ├→ AwardGranted(common, source=submission)
  ├→ [If AI_ENABLED] AI review → AwardGranted(epic, source=ai_review)
  └→ Notifications created

Teacher grades in /teacher-review UI
  ↓ POST /api/webhooks/brightspace/review
  ↓ TeacherReviewed event + AwardGranted(epic|legendary, source=teacher_review)
  ↓ Notifications created

Learner clicks "Collect" on award
  ↓ POST /api/awards/{award_id}/collect
  ↓ RewardCollected event
  ↓ [Minecraft Bridge consumes]
  ├→ Look up reward catalog (by tier)
  ├→ Get player's Minecraft username
  ├→ If online: RCON delivery immediately
  └→ If offline: Queue for next login (poll every 60s)
```

## Data Model Highlights

### Awards Table

```
id, user_id, mission_id, tier (common/epic/legendary)
source (submission/ai_review/teacher_review)
awarded_at, notified_at, collected_at (nullable)
```

- `collected_at` is NULL until learner clicks "Collect"
- Minecraft Bridge only acts on `RewardCollected` events (when collected_at is set)
- Prevents delivery before learner actively chooses to collect

### Minecraft Reward Catalog

```
tier (common/epic/legendary)
reward_type (item/effect/command)
reward (minecraft:diamond, minecraft:haste, etc.)
reward_amount, duration, persistent
```

Example rewards:
- **common**: stone (item), dirt (item)
- **epic**: diamond (8x), haste effect (5 min)
- **legendary**: netherite pickaxe, enchanted golden apple

## Troubleshooting

### Services won't start

```bash
# Check Docker resources
docker system df

# Check logs
docker compose logs web
docker compose logs postgres
docker compose logs minecraft-bridge
```

### Database not initialized

```bash
# Postgres must be up first
docker compose up -d postgres
sleep 30

# Run seed script
cd evoke-infra
python seed.py
```

### Minecraft reward not delivered

1. Check bridge logs: `docker compose logs minecraft-bridge`
2. Ensure Minecraft is running: `docker compose ps minecraft`
3. Confirm RCON password matches: `.env` RCON_PASSWORD
4. Player must be online when award is collected (or bridge queues for next login)

### AI review not triggering

```bash
# Check if enabled
docker compose ps open-webui

# Check evoke logs
docker compose logs web | grep "AI review"

# Verify OpenWebUI is accessible
curl http://localhost:3000/
```

## Configuration

### AI Mentor (B1llbot)

B1llbot is configured in OpenWebUI (not hardcoded):

1. Navigate to http://localhost:3000
2. Admin panel → Settings → Models → Add custom model
3. Name: "billbot"
4. System prompt: [Add Bill Reynolds philosophy prompt from docs/canon/billslifeprinciples.pdf](docs/canon/billslifeprinciples.pdf)
5. Knowledge base: [Connect to Keel/Basin world lore files](docs/canon/)

For now, billbot uses the underlying model (Ollama or hosted LLM) with OpenWebUI pass-through.

### Minecraft Reward Mapping

Edit `evoke-infra/init-db.sql` to change reward definitions:

```sql
INSERT INTO mc_reward_catalog 
  (campaign_id, tier, reward_type, reward, reward_amount, duration, persistent)
VALUES
  (campaign_id, 'epic', 'item', 'minecraft:diamond_pickaxe', 1, NULL, false)
```

Requires re-seeding:
```bash
docker compose down postgres
rm -r /path/to/postgres-data
docker compose up -d postgres
python seed.py
```

### Brightspace Integration (Production)

Replace `BrightspaceLMS` adapter in `main.py` to call real Brightspace API:

- LTI 1.3 login integration (already designed in `docs/process/thread3.md`)
- Award Service API for badge sync
- Dropbox submission API

For now, `brightspace-sim` is a complete stand-in using the same webhook pattern.

## Next Steps for Production

1. **LMS Integration** → Implement `BrightspaceLMS` adapter (research in thread3.md)
2. **UUID-based Minecraft Linking** → Replace username-match with Mojang UUIDs
3. **Real Auth** → Replace dev login with LTI + Brightspace identity
4. **Multi-Server Minecraft** → Support multiple Minecraft servers per organization
5. **Custom Minecraft Plugin** → Optional, for more complex reward types
6. **B1llbot Personas** → Extend OpenWebUI custom models for other NPCs (Ada, Alchemy, etc.)
7. **Offline Mobile App** → Sync with Operations Hub when back online
8. **Deployment** → AWS ECS / Kubernetes cluster (one per school/organization)

## Support

See [ARCHITECTURE.md](ARCHITECTURE.md) and [BUILD_PROMPT.md](BUILD_PROMPT.md) for more detailed context on design decisions and scope.
