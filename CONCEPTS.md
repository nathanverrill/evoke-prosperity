# CONCEPTS.md

Read this first if you are an AI assistant (or a human) picking up this repo cold. It's a glossary and orientation map, not a spec — for the real source material, follow the links.

---

## What this project is

**EVOKE** is a mission-based learning platform/engine. **EVOKE Prosperity** is the first *campaign* built on it — a 6-week, 12-mission financial-literacy and entrepreneurship curriculum wrapped in a transmedia narrative (graphic novel + web app + optional Minecraft) about a mountain town called Keel. Students aren't "doing assignments" — in the fiction, they're EVOKE Agents completing real-world missions, and the platform (web app, Minecraft, an AI mentor character) presents that work back to them as an unfolding story. See [`docs/canon/thread4.md`](docs/canon/thread4.md) for the full framing.

**Engine vs. campaign matters architecturally, not just narratively.** The codebase is meant to support future campaigns (different missions, badges, narrative) as swappable content, not by rewriting the app — see `ARCHITECTURE.md`'s "Campaigns" section. Two integrations matter here, but asymmetrically:

- **An LMS is an engine-wide invariant** — every deployment, for any campaign, has exactly one (Brightspace or Moodle). **For Evoke Prosperity, that LMS is Brightspace.**
- **Minecraft is campaign-specific** — most campaigns won't include it. Evoke Prosperity requires it, at the systems level, even though it's presented to learners as optional enrichment (no grade depends on it).

There are two things being built simultaneously, and they're documented separately:

1. **The product** — a FastAPI backend + event pipeline (currently a working prototype) that will eventually run the real curriculum.
2. **The story/curriculum** — the Evoke Prosperity campaign's 6-week, 12-mission financial-literacy curriculum.

---

## Canon hierarchy — read this before trusting any doc

`docs/` is split into three parts. **Which folder a file lives in tells you how much to trust it:**

- **[`docs/canon/`](docs/canon/README.md)** — current source of truth. If anything else conflicts with these files, these files win.
- **[`docs/legacy/`](docs/legacy/README.md)** — superseded draft material, kept for history only. **Do not treat as current.** Notably, `docs/legacy/All NPC and World Prompts/` describes a version of the world where Alpha Dynamics never left and Alex is a secret amnesiac ex-CEO — this directly contradicts canon (below) and should never be cited as fact.
- **[`docs/process/`](docs/process/thread1.md)** — meeting notes and planning chat exports. Useful history, not narrative or curriculum canon.

When in doubt, canon > process > legacy, and *within* canon, the five infographics + stakeholder feedback are the narrative spine everything else hangs off of.

---

## Story glossary (canon)

Source: [`docs/canon/1.jpg`–`5.jpg`](docs/canon/1.jpg) (the infographics) and [`docs/canon/stakeholderfeedback.md`](docs/canon/stakeholderfeedback.md).

| Term | Meaning |
|---|---|
| **Keel** (aka "Runoff") | The forgotten town at the base of the mountain. Alex's home. Struggling, but not giving up. |
| **Halyard** | The middle tier of the mountain — corporate, more advanced, but access comes at a cost (rent/fees). |
| **Oasis** | The summit — advanced, efficient, but expensive and highly pressured, not simply "utopia." |
| **Alpha Dynamics** | The corporation that built the mountain's infrastructure, then withdrew after a lithium market crash, leaving a power vacuum. |
| **The Brokers** | A faction that fills the post-Alpha vacuum and weaponizes water access via scarcity. Antagonists — leader/backstory still an open question per stakeholder feedback. |
| **Alex** | The protagonist, an "EVOKE graduate" builder from Keel. Represents curiosity/agency (exact framing still being refined — see stakeholder feedback). |
| **Ada** | Alex's remote hacker ally, based in Keel. |
| **B1llbot** | The AI mentor character. Working and live in the web app (Hub drawer, Companion Mode, `#/billbot`) via a real OpenWebUI "custom model" — see `evoke-infra/openwebui-bootstrap.py` and `GAPS.md`. In-Minecraft, currently **not loaded**: the mod's compiled bytecode targets an older Minecraft version's mappings and fails on the current one; see `evoke-infra/minecraft/Dockerfile`'s comment. Modeled on the real philosophy of **Bill Reynolds** ([`docs/canon/billslifeprinciples.pdf`](docs/canon/billslifeprinciples.pdf)) — pragmatic, understated, speaks from experience rather than lecturing. Never a narrator/teacher/quest-giver; a field guide who asks reflective questions. |
| **Alchemy** | A mysterious entity that contacts Alex near the end of the story and invites him into the global "EVOKE Network." |
| **Evokation** | A learner's final project/blueprint — the in-fiction and in-curriculum term for the culmination of the 12 missions. |
| **Basin Simulation** | The in-fiction name for the Minecraft experience — deliberately never called "the game." Strictly optional; no grade ever depends on it ([`docs/canon/thread5.md`](docs/canon/thread5.md)). |
| **Operations Hub** | The in-fiction name for the web app — framed as mission control, not an LMS. "Missions" instead of assignments, "Evidence" instead of homework, etc. |

---

## Platform / pedagogy glossary (canon)

Source: [`docs/canon/overview.md`](docs/canon/overview.md) and [`docs/canon/Prosperity Campaign Missions -- 06.11.26 .docx.txt`](docs/canon/Prosperity%20Campaign%20Missions%20--%2006.11.26%20.docx.txt) / the spreadsheet version.

| Term | Meaning |
|---|---|
| **Mission** | One of 12 curriculum activities across 6 weeks. **Technically, a mission is a Brightspace assignment** — submitting mission evidence is a normal Brightspace assignment/dropbox submission, gamified by EVOKE's framing, not an EVOKE-only record. Each has a Superpower, Primary/Secondary Evoke Skill, PFL Domain, PBL description, student-facing brief, and required Evidence. |
| **Arc** | One of 4 phases the 12 missions are grouped into: **Explore** (wk1) → **Imagine** (wk2–3) → **Act** (wk4–5) → **Communicate** (wk6). |
| **Superpower** | One of 4 badge categories a mission builds toward: Empathetic Changemaker, Systems Thinker, Creative Visionary, Deep Collaborator. |
| **PFL Domain** | The Personal Financial Literacy concept a mission teaches (Philanthropy, Goal Setting, Budgeting, Investing). |
| **Evidence** | What a learner/team submits to complete a mission — a real Brightspace assignment submission (notes, prototype, budget, pitch, etc.), which triggers the feedback loop. Not to be confused with the observation/screenshot a player records for a **Minecraft side quest** — that's a separate, Brightspace-unrelated kind of "evidence" purely for the player's own completion record. See `BUILD_PLAN.md`. |
| **Insight** | A piece of feedback on a submission — from AI Coach, instructor, or peer. Additive; nothing overwrites previous feedback. |
| **Timeline** | The per-learner, per-mission view of progress: submitted → processing → AI analysis → instructor review → completed. |
| **XP / Levels / Badges / Streaks** | Progression mechanics. XP is never removed. Streaks pause, never punish, on a missed day. |
| **Team / Venture Points / Venture Spectrum** | Teams of ~4 collaborate on missions. In the late-game "Worth Backing" / "Craft Your Pitch" missions, teams allocate 100 **Venture Points** (representing ownership/voting power) between themselves and outside backers, and classify their venture as a **Safe Bet / Balanced Bet / Moonshot**. |
| **Companion Mode** | A narrow, sidebar-style web page meant to be kept open next to the Minecraft client while playing — shows the current mission/quest, notifications, pending awards (with the same **Collect** action as the main site), and a B1llbot chat box. Same backend APIs as the main site; a separate, narrower surface, not a responsive variant. See `UI_SPEC.md`. |

---

## Technical architecture

**[`ARCHITECTURE.md`](ARCHITECTURE.md) is the target-state plan — read it before making infrastructure decisions.** Guiding principle: one senior, highly experienced engineer + an AI coding assistant can understand and run the whole thing; it runs entirely on localhost.

Quick summary of the stack (target state):

- **FastAPI** app, single process, with an in-process `asyncio` background worker (no separate worker services)
- **Redpanda** (Kafka API) — the event bus; multiple independent workers (AI Coach, Search/Timeline, and future ones) react to the same events
- **OpenSearch** — read-model projections (learner timeline, instructor dashboard, portfolio, search)
- **MinIO** — S3-compatible object storage for evidence files
- **Postgres** — identity, organizations, teams, and the mission catalog (synced from the Brightspace sim); CRUD data, not event-sourced. Built, not just planned.
- **Identity/auth** — dev-login (a `LocalIdentityProvider` equivalent) and a real `BrightspaceLTIProvider` both exist and work; there's no clean shared interface abstracting the two the way `ARCHITECTURE.md` originally sketched. Still dev-grade outside the LTI path — see `GAPS.md`'s "Auth is dev-grade" item.
- **Minecraft Reward Bridge** (`evoke-minecraft-bridge/`, Prosperity-specific) — built and running: consumes `RewardCollected` events off Redpanda and grants the matching in-game item via RCON, keyed by award tier. Also runs a heartbeat loop now: auto-links the first real Minecraft player to the seeded **Player One** account, and gives anyone online a small ongoing XP/item/AI-lore trickle — see `GAPS.md`. See `ARCHITECTURE.md`'s "Minecraft Reward Bridge" section for the original design.
- **OpenWebUI** — the AI gateway in front of Ollama/hosted models, built and running. B1llbot (web-facing; the in-Minecraft mod is currently not loaded, see the B1llbot glossary entry above) is a real "custom model" inside OpenWebUI — base model + system prompt + knowledge base(s) for RAG, provisioned by `evoke-infra/openwebui-bootstrap.py`, not a hardcoded prompt string. `AI_ENABLED=true` by default now; the local LLM backend is a containerized `ollama` service by default too (overridable to a native install).

**The currently-running code is an earlier prototype**, not yet updated to this plan — see the repo map below for what exists today versus what's planned.

---

## Repo map

```
evoke/                  FastAPI app (current prototype)
  main.py                API routes: submit-evidence, insights, timeline, instructor dashboard, portfolio
  workers.py             Background event consumer: AI Coach worker + Search/Timeline worker
  clients.py             S3/MinIO, OpenSearch, Kafka producer, AI client setup
  static/                Vanilla HTML/JS/CSS SPA (functional but minimal — one hardcoded demo learner/mission)

evoke-infra/             docker-compose for shared infra (MinIO, Redpanda, OpenSearch, Keycloak — Keycloak to be
                         replaced with Postgres per ARCHITECTURE.md)

ui/                      "Final Prosperity Showcase.html" — a polished, self-contained interactive UI mockup/prototype.
                         NOT wired to the backend. Ahead of the backend in features (XP, levels, badges, streaks,
                         Vault/portfolio, B1llbot chat UI, Profile) — treat as the target UI design, not working code.

docs/canon/              Narrative + curriculum source of truth (see Canon hierarchy above)
docs/legacy/             Superseded draft material — do not treat as current
docs/process/            Meeting notes, planning chats — history, not canon

ARCHITECTURE.md          Target-state technical architecture plan
BUILD_PLAN.md            Active build spec (infra, events, Minecraft container, Brightspace sim)
UI_SPEC.md               Gamified web experience spec + wireframe skinning contract
CONCEPTS.md              This file
```

---

## Known gaps / traps for agents

- The `ui/` mockup and the `evoke/` backend are **not connected**. Don't assume UI features (XP, badges, Vault, Profile) exist server-side just because they're in the mockup.
- [`evoke/static/script.js`](evoke/static/script.js) hardcodes `learner_id`/`mission_id` — there's no real auth or user model yet (that's what `ARCHITECTURE.md`'s Postgres + `IdentityProvider` plan addresses).
- The 12-mission curriculum is **not yet seeded** into the running backend — `main.py`'s `_bootstrap_timeline` uses a generic demo mission, not the real curriculum.
- The frontend has two health-check buttons (`/api/minio`, `/api/opensearch`) that call routes which don't exist in `main.py` — currently dead/404.
- Don't cite `docs/legacy/` as world fact. If a task needs Minecraft NPC dialogue or world details, canon (the infographics + stakeholder feedback) governs, not the legacy prompts.
