# CONCEPTS.md

Read this first if you are an AI assistant (or a human) picking up this repo cold. It's a glossary and orientation map, not a spec — for the real source material, follow the links.

---

## What this project is

**EVOKE Prosperity** is a mission-based learning platform for teaching financial literacy and entrepreneurship to students, wrapped in a transmedia narrative (graphic novel + web app + optional Minecraft). Students aren't "doing assignments" — in the fiction, they're EVOKE Agents completing real-world missions, and the platform (web app, Minecraft, an AI mentor character) presents that work back to them as an unfolding story. See [`docs/canon/thread4.md`](docs/canon/thread4.md) for the full framing.

There are two things being built simultaneously, and they're documented separately:

1. **The product** — a FastAPI backend + event pipeline (currently a working prototype) that will eventually run the real curriculum.
2. **The story/curriculum** — a 6-week, 12-mission financial-literacy curriculum wrapped in a graphic-novel narrative about a mountain town called Keel.

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
| **B1llbot** | The AI mentor character, present in both the web app and Minecraft. Modeled on the real philosophy of **Bill Reynolds** ([`docs/canon/billslifeprinciples.pdf`](docs/canon/billslifeprinciples.pdf)) — pragmatic, understated, speaks from experience rather than lecturing. Never a narrator/teacher/quest-giver; a field guide who asks reflective questions. |
| **Alchemy** | A mysterious entity that contacts Alex near the end of the story and invites him into the global "EVOKE Network." |
| **Evokation** | A learner's final project/blueprint — the in-fiction and in-curriculum term for the culmination of the 12 missions. |
| **Basin Simulation** | The in-fiction name for the Minecraft experience — deliberately never called "the game." Strictly optional; no grade ever depends on it ([`docs/canon/thread5.md`](docs/canon/thread5.md)). |
| **Operations Hub** | The in-fiction name for the web app — framed as mission control, not an LMS. "Missions" instead of assignments, "Evidence" instead of homework, etc. |

---

## Platform / pedagogy glossary (canon)

Source: [`docs/canon/overview.md`](docs/canon/overview.md) and [`docs/canon/Prosperity Campaign Missions -- 06.11.26 .docx.txt`](docs/canon/Prosperity%20Campaign%20Missions%20--%2006.11.26%20.docx.txt) / the spreadsheet version.

| Term | Meaning |
|---|---|
| **Mission** | One of 12 curriculum activities across 6 weeks. Each has a Superpower, Primary/Secondary Evoke Skill, PFL Domain, PBL description, student-facing brief, and required Evidence. |
| **Arc** | One of 4 phases the 12 missions are grouped into: **Explore** (wk1) → **Imagine** (wk2–3) → **Act** (wk4–5) → **Communicate** (wk6). |
| **Superpower** | One of 4 badge categories a mission builds toward: Empathetic Changemaker, Systems Thinker, Creative Visionary, Deep Collaborator. |
| **PFL Domain** | The Personal Financial Literacy concept a mission teaches (Philanthropy, Goal Setting, Budgeting, Investing). |
| **Evidence** | What a learner/team submits to complete a mission (notes, prototype, budget, pitch, etc.) — uploaded as a file, triggers the feedback loop. |
| **Insight** | A piece of feedback on a submission — from AI Coach, instructor, or peer. Additive; nothing overwrites previous feedback. |
| **Timeline** | The per-learner, per-mission view of progress: submitted → processing → AI analysis → instructor review → completed. |
| **XP / Levels / Badges / Streaks** | Progression mechanics. XP is never removed. Streaks pause, never punish, on a missed day. |
| **Team / Venture Points / Venture Spectrum** | Teams of ~4 collaborate on missions. In the late-game "Worth Backing" / "Craft Your Pitch" missions, teams allocate 100 **Venture Points** (representing ownership/voting power) between themselves and outside backers, and classify their venture as a **Safe Bet / Balanced Bet / Moonshot**. |

---

## Technical architecture

**[`ARCHITECTURE.md`](ARCHITECTURE.md) is the target-state plan — read it before making infrastructure decisions.** Guiding principle: one engineer + an AI coding assistant can understand and run the whole thing; it runs entirely on localhost.

Quick summary of the stack (target state):

- **FastAPI** app, single process, with an in-process `asyncio` background worker (no separate worker services)
- **Redpanda** (Kafka API) — the event bus; multiple independent workers (AI Coach, Search/Timeline, and future ones) react to the same events
- **OpenSearch** — read-model projections (learner timeline, instructor dashboard, portfolio, search)
- **MinIO** — S3-compatible object storage for evidence files
- **Postgres** *(planned, not yet in the running prototype)* — identity, organizations, teams, and the mission catalog; CRUD data, not event-sourced
- **`IdentityProvider` interface** *(planned)* — replaces Keycloak; `LocalIdentityProvider` for dev, `BrightspaceLTIProvider` sketched for later LMS integration
- **AI client** — OpenAI-compatible, points at Ollama locally or a hosted API, fully optional (`AI_ENABLED=false` by default)

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
CONCEPTS.md              This file
```

---

## Known gaps / traps for agents

- The `ui/` mockup and the `evoke/` backend are **not connected**. Don't assume UI features (XP, badges, Vault, Profile) exist server-side just because they're in the mockup.
- [`evoke/static/script.js`](evoke/static/script.js) hardcodes `learner_id`/`mission_id` — there's no real auth or user model yet (that's what `ARCHITECTURE.md`'s Postgres + `IdentityProvider` plan addresses).
- The 12-mission curriculum is **not yet seeded** into the running backend — `main.py`'s `_bootstrap_timeline` uses a generic demo mission, not the real curriculum.
- The frontend has two health-check buttons (`/api/minio`, `/api/opensearch`) that call routes which don't exist in `main.py` — currently dead/404.
- Don't cite `docs/legacy/` as world fact. If a task needs Minecraft NPC dialogue or world details, canon (the infographics + stakeholder feedback) governs, not the legacy prompts.
