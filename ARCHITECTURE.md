# EVOKE Architecture Plan

## Guiding principle

**One senior, highly experienced engineer, working with an AI coding assistant, can understand, run, debug, and extend the entire system.** This is not a bar set for an entry-level developer — it assumes someone who already has the judgment to operate Kafka-style event buses, search clusters, and object storage comfortably, and who uses that judgment to keep the system's *moving parts* few even though the operator is capable of far more complexity. Every architectural choice is judged against that bar, not against what a well-funded platform team would build. A corollary: **the whole experience runs on one computer.** Every school or campaign partner gets one server running the entire stack — app, infra, Minecraft, and the bridges between them. Cloud services (managed Postgres, real S3, hosted LLMs) are swap-in upgrades for organizations that want them, never a requirement to run the product.

Simplicity here means *each piece earns its place*, not *minimize the service count*. The engineer running this is already comfortable operating small localhost deployments of Redpanda, OpenSearch, and MinIO — so those stay. The one piece that doesn't earn its place is Keycloak: a full IAM server (its own JVM process, realms, clients, admin console, OIDC flows) is a lot of surface area for the amount of auth this project actually needs. That gets replaced with a small `IdentityProvider` interface.

This plan is a refinement of the infra sketch in [`docs/process/thread1.md`](docs/process/thread1.md) (Redpanda + MinIO + Postgres + OpenSearch + Keycloak), keeping everything except Keycloak, and adding Postgres — which today's running prototype ([evoke-infra/docker-compose.yml](evoke-infra/docker-compose.yml)) doesn't actually have yet.

---

## Campaigns: one engine, many content packs

**EVOKE Prosperity is a campaign, not the whole product.** The architecture has to support other campaigns later — different missions, different badges, different narrative — without a rearchitect. The way to do that without building a multi-tenant SaaS platform: separate the **engine** (event pipeline, identity, teams, XP/badges mechanics, submission/feedback loop, Minecraft bridge, LMS sync) from **content** (a specific campaign's missions, badges/superpowers, narrative copy, Minecraft reward mappings). The engine is campaign-agnostic; a campaign is a data bundle loaded into it.

```
campaigns              id, key (e.g. 'evoke-prosperity'), name, description
```

Every content table gains a `campaign_id` foreign key — `missions.campaign_id`, `badges.campaign_id`, `mc_reward_catalog.campaign_id` (all below). `organizations` gets an `active_campaign_id`. One deployment (one box, per the deployment model below) runs its organization's active campaign; nothing in the FastAPI app, the event catalog, or the workers needs to know *which* campaign is running — they look up missions/badges scoped to `organizations.active_campaign_id` and behave identically regardless of campaign.

This is deliberately the minimum modularity that satisfies "support other campaigns": a new campaign is a set of rows (missions, badges, reward mappings) plus narrative assets, not a code change. If a genuine need for one org to run multiple campaigns concurrently shows up later, `active_campaign_id` becomes a join table — don't build that until it's needed.

Two integrations, but they don't carry the same weight:

- **An LMS is an engine-wide invariant.** Every EVOKE deployment, for any campaign, has exactly one LMS behind it (Brightspace or Moodle) — there's no "no LMS" mode. **For Evoke Prosperity specifically, that LMS is Brightspace.**
- **Minecraft is campaign-specific, not universal.** Most campaigns won't include it. Evoke Prosperity requires it. The event-driven architecture is exactly what makes this cheap: a Minecraft Reward Bridge is just another consumer of the same `evoke-events` stream, present and enabled for campaigns that use it, simply not deployed for campaigns that don't. Nothing else in the engine needs to know whether Minecraft is in play.

Note the distinction for Minecraft specifically: *optional* describes how it's presented to the Prosperity learner (per `docs/canon/thread5.md` — no grade ever depends on it); it does not mean the integration is optional to build for this campaign. The plumbing must work end-to-end for Prosperity even though a learner can ignore it.

---

## What changes vs. today's prototype

| Today | Change | Why |
|---|---|---|
| Redpanda + Redpanda Console (event bus) | **Kept, unchanged** | Genuinely multi-consumer: AI Worker, Search/Timeline Worker, the Minecraft Reward Bridge, and the LMS sync worker all react to the same events independently. That's exactly the case an event bus is for, and the engineer already knows how to run and debug Redpanda locally. |
| OpenSearch + OpenSearch Dashboards (read models) | **Kept, unchanged** | Serves as the projection store for learner timelines, the instructor dashboard, and portfolio/search (`overview.md` §25) — already partly implemented in [workers.py](evoke/workers.py). |
| MinIO (object storage) | **Kept, unchanged** | Already S3-compatible via `boto3` ([clients.py](evoke/clients.py)); identical code path on localhost or pointed at real S3 later. |
| *(none — no relational store today)* | **Add Postgres** | System of record for campaigns, identity, organizations, teams, and content catalogs (missions, badges): structured, transactional, CRUD-shaped data that isn't naturally an event stream. Domain activity (submissions, feedback, XP, badges) stays event-sourced through Redpanda → OpenSearch, as today. |
| Keycloak (OIDC identity server) | **Replaced** with `users`/`auth_identities` tables behind a small `IdentityProvider` interface | A ~50-line adapter per identity source is easier to read, test, and extend than standing up and configuring Keycloak realms — and this project has exactly one identity source active per deployment (its LMS). |
| *(none — no LMS integration exists)* | **Add an `LMSSync` interface** with `BrightspaceLMS` and `MoodleLMS` adapters | Every deployment, for any campaign, has exactly one LMS behind it — this is an engine-level invariant, not a Prosperity-specific one. Prosperity's org config points it at `BrightspaceLMS`. |
| *(none — Minecraft assumed external)* | **Add a `minecraft` container to the same compose stack**, plus a Minecraft Reward Bridge service — **enabled for the Evoke Prosperity campaign specifically** | Minecraft is a required integration for Prosperity, not an engine-wide one. Hosting it on the same box as everything else is the target deployment for campaigns that use it. |
| AI via a direct OpenAI-compatible client (Ollama or a hosted API), raw prompt strings in `workers.py` | **Add OpenWebUI as the AI gateway** in front of Ollama/hosted models; move persona/prompt/knowledge-base config into OpenWebUI "custom models" instead of Python strings | See the dedicated "AI backend: OpenWebUI" section below. |

Net effect on `evoke-infra/docker-compose.yml`: swap Keycloak for Postgres, add a `minecraft` service. Same "one `docker compose up`" operational shape you already know.

---

## System diagram

```
                        ┌─────────────────────────┐
                        │   Browser (static SPA)  │
                        └────────────┬────────────┘
                                     │ HTTP
                        ┌────────────▼─────────────────────────┐
                        │           FastAPI app                 │
                        │        (evoke/main.py)                │
                        │                                        │
                        │  Identity / org / team / campaign       │
                        │  content reads & writes → Postgres      │
                        │                                        │
                        │  Domain commands (submit evidence,      │
                        │  publish insight) → publish to Redpanda │
                        └───────┬───────────────────────┬────────┘
                                │                        │
                      ┌─────────▼─────────┐   ┌──────────▼──────────┐
                      │     Postgres        │   │      Redpanda        │
                      │  campaigns, users,   │   │  evoke-events topic   │
                      │  auth_ids, orgs,     │   │  (unchanged)          │
                      │  teams, missions,    │   └──────────┬──────────┘
                      │  badges,             │              │
                      │  minecraft_links,    │   ┌──────────┼──────────────────────────┐
                      │  mc_reward_grants    │   │          │                          │
                      └─────────────────────┘   │          │                          │
                                       ┌──────────▼─────────┐  ┌────────▼─────────┐ ┌───▼─────────────┐
                                       │  Background workers │  │ Minecraft Reward  │ │  LMS Sync        │
                                       │  (AI Worker,         │  │ Bridge            │ │  worker          │
                                       │   Search/Timeline    │  │                   │ │                  │
                                       │   Worker — same      │  │ consumes          │ │ consumes         │
                                       │   asyncio task as    │  │ BadgeAwarded /    │ │ BadgeAwarded /   │
                                       │   today's             │  │ XPGranted,        │ │ MissionCompleted,│
                                       │   workers.py)        │  │ talks RCON        │ │ calls Brightspace │
                                       └─────────┬──────────┘  └────────┬──────────┘ │ or Moodle API    │
                                                  │                     │            └──────────────────┘
                                       ┌──────────┼───────────┐        │
                                       │          │           │  ┌─────▼─────┐
                                 ┌─────▼─────┐┌───▼──────┐┌───▼────┐│ Minecraft  │
                                 │ OpenSearch ││  MinIO   ││Redpanda││ server     │
                                 │ (timeline, ││(evidence ││(new    ││ (same box, │
                                 │ dashboard, ││ files)   ││events  ││ RCON on    │
                                 │ portfolio) ││          ││out)    ││ localhost) │
                                 └───────────┘└──────────┘└────────┘└───────────┘

        FastAPI app + AI Worker + Minecraft Reward Bridge all call out to:

                              ┌─────────────────────────┐
                              │        OpenWebUI          │
                              │  (OpenAI-compatible API)  │
                              │                            │
                              │  "custom models":          │
                              │   billbot (system prompt   │
                              │   + knowledge base), and    │
                              │   any other AI mentor/NPC   │
                              └─────────────┬─────────────┘
                                            │
                                  ┌─────────▼─────────┐
                                  │  Ollama (host) or   │
                                  │  a hosted LLM API    │
                                  └─────────────────────┘

                        ── all of the above run on one server, per organization ──
```

Same process shape as today for the core app — one FastAPI process, one `asyncio` background task ([main.py:221-223](evoke/main.py)). The Minecraft Reward Bridge and LMS Sync worker are two small, genuinely separate services (reasons below), both driven by the same Redpanda event stream everything else already uses. OpenWebUI is a shared dependency any of these can call — see below.

---

## Data model

### Postgres — campaigns, identity, organizations, teams, content catalogs

Structured reference/admin data. Transactional, queried directly (no event indirection needed for CRUD like "add a team member").

```
campaigns              id, key, name, description
                       -- 'evoke-prosperity' is the first row, not a special case in code

organizations          id, name, active_campaign_id,
                       lms_type ('brightspace' | 'moodle')   -- required: every org has exactly one

users                  id, org_id, display_name, email, role ('learner' | 'instructor' | 'admin')
auth_identities        user_id, provider ('local' | 'brightspace' | 'moodle'),
                       provider_subject, password_hash (nullable)

teams                  id, org_id, name
team_members           team_id, user_id, role_label (free text: 'Leader', 'Researcher', ...)

missions               id, campaign_id, week, sequence, title, arc ('Explore'|'Imagine'|'Act'|'Communicate'),
                       superpower, primary_skill, secondary_skill, pfl_domain,
                       pbl_description, mission_brief_md, evidence_requirements_md
                       -- seeded once from docs/canon/Evoke 12 Mission Detailed Summary... for the
                       -- 'evoke-prosperity' campaign; a new campaign seeds its own rows

badges                 id, campaign_id, key, name, category
                       -- Prosperity's four Superpowers are rows here, not a hardcoded enum

minecraft_links        user_id, server_id, minecraft_uuid, minecraft_username (cached), linked_at
                       -- one row per (user, server); see "Minecraft Reward Bridge" below

mc_reward_catalog      id, campaign_id, badge_id (nullable, FK → badges),
                       reward_type ('item'|'effect'|'command'), reward (e.g. 'minecraft:iron_pickaxe'),
                       reward_amount, duration, persistent (bool), reward_tier
                       -- content, not code: which in-game reward a given badge/event maps to,
                       -- per campaign

mc_reward_grants       user_id, server_id, catalog_id, granted_at, active, executed
                       -- delivery ledger; mirrors the proven pattern in the reference Badge-API
```

`missions.id` is what event payloads (`mission_id`) and OpenSearch documents reference — Postgres is the source of truth for *what a mission is*; OpenSearch tracks *how a given learner is doing on it*.

### Redpanda → OpenSearch — the event stream and its projections

Unchanged from today's pattern in [workers.py](evoke/workers.py). Event catalog (per [`overview.md`](docs/canon/overview.md) §17):

```
EvidenceSubmitted, TeamEvidenceSubmitted, FeedbackGenerated, InsightPublished,
BadgeAwarded, XPGranted, QuestCompleted, MissionCompleted, ...
```

Projected by workers into OpenSearch indices:

- `learner-timeline` — per `(learner_id, mission_id)`: status, timeline steps, insights, XP, badges (as today)
- `instructor-dashboard` — per mission, aggregated across learners
- `portfolio` — per learner, aggregated across missions
- full-text search across missions/evidence/reflections (`overview.md` §25)

Both the Minecraft Reward Bridge and the LMS Sync worker are additional consumers of this same stream — no new event infrastructure, just new subscribers.

### MinIO — evidence files

Unchanged. Referenced by `object_key` in event payloads, exactly as today.

---

## Identity & LMS integration

**Every EVOKE deployment, for any campaign, has exactly one LMS behind it — Brightspace or Moodle, never neither.** This is an engine-level invariant, so `organizations.lms_type` is non-nullable. **For Evoke Prosperity specifically, that LMS is Brightspace** — Moodle support exists in the engine for other campaigns/organizations, not because Prosperity needs a choice. Two related but distinct adapter interfaces, because "log a user in" and "push progress back to the LMS" are different capabilities:

```python
class IdentityProvider(Protocol):
    def login(...) -> User: ...
    def get_user(...) -> User: ...

class LMSSync(Protocol):
    def submit_assignment(user: User, mission: Mission, file: bytes) -> None: ...
    def push_badge_award(user: User, badge: Badge) -> None: ...
    def push_mission_status(user: User, mission: Mission, status: str) -> None: ...
```

**Missions are modeled as Brightspace assignments, not a parallel EVOKE-native record.** Each `missions` row carries an `lms_assignment_ref` — the assignment/dropbox this mission is bound to. Submitting evidence through the EVOKE UI calls `submit_assignment`, which is a real Brightspace Dropbox submission with EVOKE's mission framing on top of it — a normal homework-upload flow, gamified. This is also why teacher review is naturally a Brightspace-side action (a teacher grading a Brightspace assignment in the gradebook, as they always do) rather than an EVOKE-specific review screen: `push_mission_status`/grading feedback flows back through the same adapter.

- **`BrightspaceLMS`** — implements all three. Identity via LTI launch; assignment submission and progress sync via the standard Brightspace assignment/Dropbox and Award Service APIs (`POST /d2l/api/bas/{version}/orgunits/{orgUnitId}/issued/`), per the research already done in [`docs/process/thread3.md`](docs/process/thread3.md). Brightspace Groups can later sync into `teams`/`team_members` the same way.
- **`MoodleLMS`** — implements both. **Needs its own research pass**, analogous to `thread3.md`'s Brightspace research — Moodle can act as an LTI 1.3 Platform for identity, and exposes a web services API (`webservice/rest/server.php`) plus a badges subsystem for progress/badge sync. Treat the exact endpoints as unconfirmed until that research is done; don't build against guessed API shapes.
- **`LocalIdentityProvider`** — email + password or a dev auto-login, backed by Postgres `users`/`auth_identities`. Exists strictly for local development against a deployment not yet pointed at a real school's LMS. It is **not** a supported "no LMS" production mode for any campaign — every real deployment has Brightspace or Moodle behind it. That's a real difference from the more permissive accessibility ladder sketched in [`docs/canon/thread6.md`](docs/canon/thread6.md), which described optional/offline modes for other platform features, not the LMS itself.

An `LMSSync` implementation is a consumer of the same Redpanda `evoke-events` stream as everything else — architecturally identical to the Minecraft Reward Bridge below: a small service that reacts to `BadgeAwarded`/`MissionCompleted` and calls an external API. No IAM server to run, configure, or explain — just Postgres rows and one adapter per LMS.

---

## AI backend: OpenWebUI

Today's prototype ([clients.py](evoke/clients.py), [workers.py](evoke/workers.py)) talks to a raw OpenAI-compatible endpoint (Ollama or a hosted API) and hardcodes B1llbot's system prompt as a Python string. **OpenWebUI sits in front of that instead**, as the shared AI gateway for the whole engine — for ease of use, and because it turns "who is B1llbot" into content instead of code.

- **OpenWebUI runs as a container** in the same one-box-per-organization stack, pointed at Ollama (on the host, as today) or a hosted model. It exposes an OpenAI-compatible API, so the FastAPI app's AI client barely changes — just `base_url` now points at OpenWebUI instead of Ollama directly.
- **B1llbot is a "custom model" configured inside OpenWebUI**: a base model + a system prompt + one or more attached knowledge bases (RAG) that give him his lore/character grounding — configured through OpenWebUI's admin UI, not embedded in `workers.py`. The AI Coach worker calls `model="billbot"` (or whatever key the campaign configures) instead of building a prompt string itself.
- **The same pattern covers any other AI agent/assistant/NPC** a campaign wants — each is just another named custom model in OpenWebUI (its own system prompt + knowledge base), called the same way. This is what makes character personas swappable per campaign without touching engine code, consistent with the campaign/content split above.
- If Minecraft NPC dialogue is built later (distinct from the reward-granting concern below), it follows the same path: whatever relays in-game chat calls OpenWebUI with the relevant NPC's model key, exactly like the web app's AI Coach does.
- Nothing about this needs new Postgres tables — model/prompt/knowledge-base configuration lives inside OpenWebUI's own storage, not ours. The engine only needs to know *which model key* to call for a given purpose (an env var or a per-campaign config value, e.g. `AI_COACH_MODEL=billbot`).

---

## Minecraft Reward Bridge

**Requirement, for the Evoke Prosperity campaign**: when a learner earns a badge in the LMS/Operations Hub, the corresponding item, potion effect, or in-game command is granted to their Minecraft character automatically — whether they're online at the time or not. This is a required integration for the Prosperity campaign, even though Minecraft itself is presented to learners as optional enrichment (per `docs/canon/thread5.md`, no grade ever depends on it).

The team already has a working reference implementation of this exact mechanism at `evoke-cu-internship/badges/Badge-API` (Flask + SQLite + a hand-rolled RCON client, built to bridge Moodle to Minecraft). The design below reuses its proven parts, adapted to this project's stack (a small FastAPI-adjacent service, Postgres instead of SQLite, driven by Redpanda events instead of a webhook/manual frontend).

### Deployment target: same box as the app, per organization

Per the "one server per partner" deployment model, the Minecraft server is a container in the same compose stack as everything else — not a separately hosted server the bridge reaches over the network. `server_id` still exists in the data model (a school could in principle run more than one world/cohort), but the default and recommended shape is one Minecraft server per organization, on the same machine.

### Why the bridge is still its own small service, not a feature bolted into `main.py`

- It needs a long-lived RCON socket connection and two polling loops (player presence, reward delivery) — a different runtime shape than a request/response API.
- Per "Optional integrations stay at arm's length" (below): if a given organization somehow disables Minecraft, this service simply isn't running. Nothing else in the platform notices.

### How it works (carried over from the reference implementation)

1. **Presence polling** — a loop periodically runs the RCON `list` command against the local Minecraft server and upserts `minecraft_links.minecraft_username`/last-seen.
2. **Reward catalog** — `mc_reward_catalog` is the same shape as the reference's `rewards.json`: `reward_type` of `item` (an RCON `give`), `effect` (an RCON `effect give`, with `persistent` rewards re-applied if the player logs back in and the effect has worn off), or `command` (an arbitrary RCON command with a `<player>` placeholder — e.g. a currency grant). This is content, editable per campaign without touching bridge code.
3. **Grant + delivery loop** — the bridge subscribes to `BadgeAwarded` (and any other reward-worthy event) on the existing Redpanda `evoke-events` topic. On receipt, it looks up `mc_reward_catalog` for that badge, inserts a row into `mc_reward_grants` (`active=1, executed=0`), and immediately attempts delivery via RCON if the player is online. A second loop (same idea as the reference's `reward_scheduler.py`) runs every ~60s, re-checking presence and:
   - delivering any `executed=0` grants to players who are now online (covers "badge earned while offline")
   - re-applying `persistent` rewards to online players if the effect isn't currently active (covers "server restarted" / "effect expired")
4. Nothing here needs a custom Minecraft plugin — RCON + vanilla commands is enough, matching the reference implementation and keeping the Minecraft-server side untouched.

### One upgrade over the reference implementation: identity

The reference implementation matches players by **raw Minecraft username**, which is simple but not durable (usernames can change; Mojang UUIDs don't). `minecraft_links` stores `minecraft_uuid` as the real key, with `minecraft_username` cached for RCON calls (RCON's `list` only returns usernames — resolving UUID happens once, at link time, via an account-linking flow: the player visits a `/link <code>` URL to associate their EVOKE account with their Minecraft UUID, per `docs/process/thread2.md`). For an MVP, matching on username like the reference implementation is an acceptable first cut — just plan to backfill the UUID link before scaling past a single pilot server.

---

## Deployment

**Deployment model: one server per organization.** Every school or campaign partner runs the entire stack on one machine — there is no shared multi-tenant backend. This is what makes "runs on one computer" true in production, not just in local dev.

`evoke-infra/docker-compose.yml`: drop `keycloak`, add `postgres`, `open-webui`, and (for campaigns that use it, e.g. Prosperity) `minecraft`. Everything else — `minio`, `redpanda`, `redpanda-console`, `opensearch`, `opensearch-dashboards` — stays as-is:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: ${INFRA_SECRET:-devsecret123}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    ports:
      - "${PORT_POSTGRES:-5432}:5432"

  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    environment:
      # As actually shipped: defaults to a containerized `ollama` service
      # (${OLLAMA_BASE_URL:-http://ollama:11434}) so a fresh clone needs no
      # native install; override to host.docker.internal:11434 for a
      # faster native Ollama (Mac especially -- Docker Desktop can't pass
      # Metal/GPU through to a container there), or to a hosted
      # OpenAI-compatible endpoint for production (see HOSTING_COST_MODEL.md).
      OLLAMA_BASE_URL: ${OLLAMA_BASE_URL:-http://ollama:11434}
    ports:
      - "${PORT_OPENWEBUI:-3000}:8080"
    volumes:
      - openwebui-data:/app/backend/data   # custom model configs, prompts, knowledge bases

  minecraft:   # only for campaigns that use it — e.g. Evoke Prosperity
    image: itzg/minecraft-server   # widely used, supports Paper/Fabric, RCON via env vars
    environment:
      EULA: "TRUE"
      ENABLE_RCON: "true"
      RCON_PASSWORD: ${INFRA_SECRET:-devsecret123}
    ports:
      - "${PORT_MINECRAFT:-25565}:25565"
    volumes:
      - minecraft-data:/data

  # minio, redpanda, redpanda-console, opensearch, opensearch-dashboards: unchanged
```

`evoke/docker-compose.yml` adds `POSTGRES_*` connection env vars alongside the existing `REDPANDA_BROKER`/`OPENSEARCH_NODE`/`MINIO_*` vars, plus `LMS_TYPE` (`brightspace` for Prosperity) and that LMS's credentials, plus `RCON_*` vars for campaigns using Minecraft. The AI client's `base_url` moves from Ollama directly to `OPENWEBUI_BASE_URL`, and its `model` becomes a per-purpose custom-model key (e.g. `AI_COACH_MODEL=billbot`) instead of a raw base model name. `docker compose up -d` in each folder is still the whole setup.

`AI_ENABLED=false` by default remains the escape hatch — unchanged.

---

## Optional integrations stay at arm's length

Per [`docs/canon/thread5.md`](docs/canon/thread5.md), nothing about Minecraft becomes a dependency **for the learner's experience** — no grade or mission completion ever requires it. That is a UX/pedagogy guarantee, not a statement about whether the system builds and runs it. For the Prosperity campaign, both of the below are required, always-on parts of the deployment:

- **Minecraft Reward Bridge**: see the dedicated section above. Consumes `BadgeAwarded`/reward events from Redpanda and calls RCON against the same-box Minecraft server; can also read mission state or post side-quest completions back as ordinary events. Required for Prosperity; simply not deployed for a campaign that doesn't use Minecraft.
- **LMS Sync (`BrightspaceLMS`)**: see "Identity & LMS integration" above. Consumes `BadgeAwarded`/`MissionCompleted` and calls Brightspace's API. Required for every campaign, per the engine-level LMS invariant — not specific to Prosperity.

What stays genuinely optional, campaign to campaign, is Minecraft — that's exactly what the campaign/content split above is for. A campaign without Minecraft simply doesn't populate `mc_reward_catalog` and doesn't run the bridge. The LMS is never optional at the engine level, only *which* LMS (`BrightspaceLMS` vs `MoodleLMS`) varies.

---

## Deliberately not doing (and why)

- **No Keycloak.** A ~50-line adapter interface per identity source covers local dev, Brightspace, and Moodle. Add a real IdP only if a future requirement can't be met by an `IdentityProvider`/`LMSSync` implementation.
- **No multi-tenant backend.** One organization, one server, one active campaign at a time. Simpler to reason about, and matches "runs on one computer" literally instead of figuratively.
- **No frontend build pipeline.** Static HTML/JS served by FastAPI's `StaticFiles`, as today.
- **No event-sourcing identity/org/team/campaign data.** Auth, org, team membership, and campaign/mission/badge catalogs are ordinary CRUD against Postgres, not events on the Redpanda topic — they don't need replay, multi-consumer fan-out, or eventual consistency, and modeling them as events would just make simple lookups indirect for no benefit.
- **No custom Minecraft plugin.** RCON + vanilla commands, per the proven reference implementation. Revisit only if a specific reward or interaction genuinely can't be expressed as an RCON command.
- **No hardcoded AI personas in application code.** B1llbot's (and any other AI character's) system prompt and knowledge base live in OpenWebUI as a custom model, not as a Python string in `workers.py`. Swapping or tuning a character is a content change, not a deploy.

---

## Migration path from the current prototype

1. **Stand up Postgres** in `evoke-infra`; add `campaigns` / `organizations` / `users` / `auth_identities` / `teams` / `team_members` / `missions` / `badges` tables.
2. **Seed one campaign row** (`evoke-prosperity`) and its **missions**/**badges** from [`docs/canon/Evoke 12 Mission Detailed Summary revision bf v2.xlsx - Google Sheets.pdf`](docs/canon/Evoke%2012%20Mission%20Detailed%20Summary%20revision%20bf%20v2.xlsx%20-%20Google%20Sheets.pdf) and `overview.md`'s four Superpowers — a one-time script, not a runtime dependency.
3. **Add the `IdentityProvider`/`LMSSync` interfaces** with `LocalIdentityProvider` first (for dev); wire session cookies into the existing endpoints; replace hardcoded `learner_id`/`mission_id` strings in [script.js](evoke/static/script.js) with a real logged-in user.
4. **Remove `keycloak`** from `evoke-infra/docker-compose.yml`.
5. Redpanda, OpenSearch, and MinIO need no migration — they keep doing exactly what they do today.
6. **Add `open-webui`** to the compose stack, pointed at the existing Ollama host; configure B1llbot as a custom model (system prompt + knowledge base) inside it; update the AI Coach worker to call OpenWebUI with `model="billbot"` instead of building a raw prompt string.
7. **Add the `minecraft` container** (Prosperity only) to the compose stack; **build the Minecraft Reward Bridge**, adapting the proven RCON client + reward-scheduler logic from `evoke-cu-internship/badges/Badge-API`, swapping Flask/SQLite for Postgres + a Redpanda consumer.
8. **Implement `BrightspaceLMS`** (research already done, `thread3.md`) — LTI login + Award Service badge sync. This is the LMS every Prosperity deployment uses.
9. **Research and implement `MoodleLMS`** for future non-Prosperity campaigns — this is new research, not yet started; budget it as its own task before committing to specific API calls. Not on the critical path for Prosperity.

---

## Testing & observability, sized to one engineer

- `pytest` against the FastAPI app; Postgres for relational logic, a throwaway Redpanda topic + OpenSearch index for event/projection logic (same as would be needed today).
- Structured logging to stdout; `docker logs` plus Redpanda Console (already in the stack) for inspecting the event stream — no new tooling introduced.
- Postgres stays simple enough to inspect with `psql` directly; no ORM migrations system needed beyond a plain SQL schema file until the data model outgrows that.
- The Minecraft Reward Bridge and LMS Sync worker are both small enough to unit test by mocking the RCON socket / LMS HTTP client respectively — no test Minecraft server or test LMS tenant required for most of their logic.
- The AI Coach worker only needs to mock OpenWebUI's OpenAI-compatible endpoint — persona/prompt/knowledge-base behavior lives in OpenWebUI itself and isn't something the app's test suite needs to exercise.
