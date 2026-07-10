# EVOKE Architecture Plan

## Guiding principle

**One engineer, working with an AI coding assistant, can understand, run, debug, and extend the entire system.** Every architectural choice is judged against that bar, not against what a well-funded platform team would build. A corollary: **the whole stack runs on localhost with zero required cloud dependencies.** Cloud services (managed Postgres, real S3, hosted LLMs) are swap-in upgrades for production, never a requirement to develop or demo the product.

Simplicity here means *each piece earns its place*, not *minimize the service count*. The engineer running this is already comfortable operating small localhost deployments of Redpanda, OpenSearch, and MinIO — so those stay. The one piece that doesn't earn its place is Keycloak: a full IAM server (its own JVM process, realms, clients, admin console, OIDC flows) is a lot of surface area for the amount of auth this project actually needs today. That gets replaced with a small `IdentityProvider` interface.

This plan is a refinement of the infra sketch in [`docs/process/thread1.md`](docs/process/thread1.md) (Redpanda + MinIO + Postgres + OpenSearch + Keycloak), keeping everything except Keycloak, and adding Postgres — which today's running prototype ([evoke-infra/docker-compose.yml](evoke-infra/docker-compose.yml)) doesn't actually have yet.

---

## What changes vs. today's prototype

| Today | Change | Why |
|---|---|---|
| Redpanda + Redpanda Console (event bus) | **Kept, unchanged** | This is genuinely a multi-consumer system: AI Worker, Search/Timeline Worker, and (per [`overview.md`](docs/canon/overview.md) §17) future Portfolio/Notification/Badge workers all react to the same events independently. That's exactly the case an event bus is for, and the engineer already knows how to run and debug Redpanda locally. |
| OpenSearch + OpenSearch Dashboards (read models) | **Kept, unchanged** | Serves as the projection store for learner timelines, the instructor dashboard, and portfolio/search (`overview.md` §25) — already partly implemented in [workers.py](evoke/workers.py). |
| MinIO (object storage) | **Kept, unchanged** | Already S3-compatible via `boto3` ([clients.py](evoke/clients.py)); identical code path on localhost or pointed at real S3 later. |
| *(none — no relational store today)* | **Add Postgres** | The prototype currently has no persistent identity/team/org model at all — `script.js` hardcodes `learner_id`/`mission_id` strings. Postgres becomes the system of record for identity, organizations, teams, and the mission catalog: structured, transactional, CRUD-shaped data that isn't naturally an event stream. Domain activity (submissions, feedback, XP, badges) stays event-sourced through Redpanda → OpenSearch, as today. |
| Keycloak (OIDC identity server) | **Replaced** with a `users`/`auth_identities` table in Postgres behind a small `IdentityProvider` interface | One IAM server's worth of operational surface for what is, right now, "local dev login" plus (later) one LMS's LTI launch. A ~50-line adapter is easier to read, test, and extend than standing up and configuring Keycloak realms. |
| AI via OpenAI-compatible client, `AI_ENABLED` flag | **Kept, unchanged** | Already the right shape: one client, pointed at Ollama locally or a hosted API in prod, fully optional. |

Net effect on `evoke-infra/docker-compose.yml`: **swap Keycloak for Postgres.** Same number of containers, same operational shape you already know — just no JVM-based IAM server to configure.

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
                        │  Identity / org / team / mission-catalog│
                        │  reads & writes go straight to Postgres │
                        │                                        │
                        │  Domain commands (submit evidence,      │
                        │  publish insight) → publish to Redpanda │
                        └───────┬───────────────────────┬────────┘
                                │                        │
                      ┌─────────▼─────────┐   ┌──────────▼──────────┐
                      │     Postgres        │   │      Redpanda        │
                      │  users, auth_ids,    │   │  evoke-events topic   │
                      │  organizations,      │   │  (unchanged)          │
                      │  teams, missions     │   └──────────┬──────────┘
                      │  (catalog)           │              │
                      └─────────────────────┘     ┌─────────▼──────────┐
                                                   │  Background workers │
                                                   │  (AI Worker,         │
                                                   │   Search/Timeline    │
                                                   │   Worker — same      │
                                                   │   asyncio task as    │
                                                   │   today's            │
                                                   │   workers.py)        │
                                                   └─────────┬──────────┘
                                                              │
                                        ┌─────────────────────┼───────────────┐
                                        │                     │               │
                                  ┌─────▼─────┐        ┌──────▼─────┐   ┌─────▼─────┐
                                  │ OpenSearch  │        │   MinIO     │   │ Redpanda   │
                                  │ (timeline,  │        │ (evidence   │   │ (new       │
                                  │ dashboard,  │        │  files)     │   │  events    │
                                  │ portfolio)  │        │             │   │  out)      │
                                  └────────────┘        └────────────┘   └────────────┘
```

Same process shape as today — one FastAPI app, one `asyncio` background task ([main.py:221-223](evoke/main.py)) — with a new Postgres connection alongside the existing Kafka/OpenSearch/MinIO clients in [clients.py](evoke/clients.py).

---

## Data model

### Postgres — identity, organizations, teams, mission catalog

Structured reference/admin data. Transactional, queried directly (no event indirection needed for CRUD like "add a team member").

```
organizations         id, name, lms_type (nullable: 'brightspace' | null)

users                 id, org_id, display_name, email, role ('learner' | 'instructor' | 'admin')
auth_identities        user_id, provider ('local' | 'brightspace' | 'google'),
                       provider_subject, password_hash (nullable)

teams                  id, org_id, name
team_members           team_id, user_id, role_label (free text: 'Leader', 'Researcher', ...)

missions               id, week, sequence, title, arc ('Explore'|'Imagine'|'Act'|'Communicate'),
                       superpower, primary_skill, secondary_skill, pfl_domain,
                       pbl_description, mission_brief_md, evidence_requirements_md
                       -- seeded once from docs/canon/Evoke 12 Mission Detailed Summary...
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

### MinIO — evidence files

Unchanged. Referenced by `object_key` in event payloads, exactly as today.

---

## Auth

A minimal `IdentityProvider` interface (mirrors the adapter idea already sketched in [`docs/process/thread2.md`](docs/process/thread2.md)):

```python
class IdentityProvider(Protocol):
    def login(...) -> User: ...
    def get_user(...) -> User: ...
```

- **`LocalIdentityProvider`** — email + password (or a dev auto-login), hashed with `passlib`, session via signed cookie, backed by Postgres `users`/`auth_identities`. This is all that's needed to run entirely on localhost.
- **`BrightspaceLTIProvider`** (later) — implements the same interface; on LTI launch, upserts a `users` row and an `auth_identities` row with `provider = 'brightspace'`. `organizations.lms_type` flags which orgs use it. Nothing else in the app changes — the rest of the system only ever sees a `User`, never an auth provider detail. Brightspace Groups (per [`docs/process/thread3.md`](docs/process/thread3.md)) can later sync into `teams`/`team_members` the same way.

No IAM server to run, configure, or explain — just Postgres rows and a small adapter per identity source.

---

## Deployment

`evoke-infra/docker-compose.yml`: drop `keycloak`, add `postgres`. Everything else — `minio`, `redpanda`, `redpanda-console`, `opensearch`, `opensearch-dashboards` — stays as-is:

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

  # minio, redpanda, redpanda-console, opensearch, opensearch-dashboards: unchanged
```

`evoke/docker-compose.yml` adds a `POSTGRES_*` connection alongside the existing `REDPANDA_BROKER`/`OPENSEARCH_NODE`/`MINIO_*` env vars. `docker compose up -d` in each folder is still the whole setup.

Ollama, if enabled, keeps running on the host (`OLLAMA_BASE_URL=http://host.docker.internal:11434/v1`), `AI_ENABLED=false` by default — unchanged.

---

## Optional integrations stay at arm's length

Per [`docs/canon/thread5.md`](docs/canon/thread5.md) and [`thread6.md`](docs/canon/thread6.md), nothing outside the core loop becomes a dependency. Each of these talks to the core through the same API/events/tables the rest of the app uses:

- **Minecraft bridge**: maps `minecraft_uuid ↔ user_id` (a row in Postgres), calls the existing REST API to read mission state or post side-quest completions as ordinary events. Can be absent entirely without affecting the core curriculum.
- **Brightspace LTI**: an `IdentityProvider` implementation (above) plus a sync job that reads `BadgeAwarded`/XP projections from OpenSearch and calls Brightspace's Award Service API (per [`docs/process/thread3.md`](docs/process/thread3.md)).

---

## Deliberately not doing (and why)

- **No Keycloak.** A ~50-line adapter interface covers local dev and Brightspace LTI. Add a real IdP only if a future customer requires SSO that can't be met by an `IdentityProvider` implementation.
- **No microservices beyond the existing worker pattern.** One FastAPI app, one background task, the same shape as today. Split a piece out (e.g., a Minecraft bridge on its own host) only when it has a genuinely different scaling or deployment profile.
- **No frontend build pipeline.** Static HTML/JS served by FastAPI's `StaticFiles`, as today.
- **No event-sourcing identity/org/team data.** Auth, org, and team membership are ordinary CRUD against Postgres, not events on the Redpanda topic — they don't need replay, multi-consumer fan-out, or eventual consistency, and modeling them as events would just make simple lookups indirect for no benefit.

---

## Migration path from the current prototype

1. **Stand up Postgres** in `evoke-infra`; add the `organizations` / `users` / `auth_identities` / `teams` / `team_members` / `missions` tables.
2. **Seed `missions`** from [`docs/canon/Evoke 12 Mission Detailed Summary revision bf v2.xlsx - Google Sheets.pdf`](docs/canon/Evoke%2012%20Mission%20Detailed%20Summary%20revision%20bf%20v2.xlsx%20-%20Google%20Sheets.pdf) — a one-time script, not a runtime dependency.
3. **Add the `IdentityProvider` interface** with `LocalIdentityProvider` only; wire session cookies into the existing endpoints; replace hardcoded `learner_id`/`mission_id` strings in [script.js](evoke/static/script.js) with a real logged-in user.
4. **Remove `keycloak`** from `evoke-infra/docker-compose.yml`.
5. Redpanda, OpenSearch, and MinIO need no migration — they keep doing exactly what they do today.
6. `BrightspaceLTIProvider` and the Minecraft bridge are added later, as adapters, only when there's a concrete need driving them.

---

## Testing & observability, sized to one engineer

- `pytest` against the FastAPI app; Postgres for relational logic, a throwaway Redpanda topic + OpenSearch index for event/projection logic (same as would be needed today).
- Structured logging to stdout; `docker logs` plus Redpanda Console (already in the stack) for inspecting the event stream — no new tooling introduced.
- Postgres stays simple enough to inspect with `psql` directly; no ORM migrations system needed beyond a plain SQL schema file until the data model outgrows that.
