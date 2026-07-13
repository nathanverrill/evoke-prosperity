# EVOKE Prosperity

A mission-based learning platform for teaching financial literacy and entrepreneurship, wrapped in a transmedia narrative (graphic novel + web app + optional Minecraft). Students complete real-world "missions" that are presented back to them as an unfolding story rather than assignments.

**New to this repo?** Read [`CONCEPTS.md`](CONCEPTS.md) first — it's a glossary and orientation map (story terms, curriculum terms, canon vs. legacy docs, repo layout) written for anyone or any AI assistant picking this up cold. Then [`GAPS.md`](GAPS.md) for an honest, current audit of what's built vs. still open — it's kept up to date far more actively than any prose summary would stay accurate.

---

## Quickstart

```
./quick-start.sh
```

Brings up both Docker Compose stacks (`evoke-infra` then `evoke`), seeds the database, and prints access points. Then open [http://localhost:8000](http://localhost:8000) — you're auto-signed-in as **Player One**, one of two seeded default users (the other, **Admin**, is reachable at `/api/dev-login?email=admin@evoke.local` — no login UI for it yet).

To reach it from another device on your network (a phone, to test Minecraft/Bedrock), use your machine's LAN IP instead of `localhost`.

AI feedback (the AI Coach on submissions, B1llbot chat) is on by default (`AI_ENABLED=true`) and needs a local LLM backend — `evoke-infra/docker-compose.yml` includes a containerized `ollama` service that pulls a model automatically on first boot, so this works out of the box. If you already run Ollama natively (faster on Mac, since Docker Desktop can't pass Metal/GPU through to a container there), override `OLLAMA_BASE_URL=http://host.docker.internal:11434` in a local `.env`.

**One more one-time step for B1llbot specifically:** run `python3 evoke-infra/openwebui-bootstrap.py` once the stack is up. It creates B1llbot's persona (system prompt + knowledge base) inside OpenWebUI — without it, OpenWebUI has a base model but no "billbot" character configured, and B1llbot chat will error.

Minecraft (optional, Prosperity-specific) comes up as part of `evoke-infra`. See `evoke-infra/minecraft/world-seed/README.md` for loading the real Basin Simulation world instead of a fresh vanilla one. The first real player to connect gets auto-linked to Player One — no manual account-linking needed to see rewards, XP, and B1llbot lore messages actually arrive in-game.

---

## Repo layout

```
evoke/          FastAPI backend + vanilla-JS SPA — see evoke/main.py, workers.py, clients.py, static/
evoke-infra/    Shared infrastructure: Postgres, MinIO, Redpanda, OpenSearch, OpenWebUI, Ollama, Minecraft (docker-compose)
brightspace-sim/ Brightspace LMS simulator (real Brightspace API shapes) -- system of record for the 12 missions in dev
evoke-minecraft-bridge/ Consumes RewardCollected events (delivers via RCON) + a heartbeat loop (auto-links the first player, online XP/items/AI lore)
ui/             Older polished interactive UI mockup -- design reference for flow/feature set, not current code
docs/           Narrative, curriculum, and planning source material -- see docs/README.md
```

- [`CONCEPTS.md`](CONCEPTS.md) — glossary and orientation (start here)
- [`GAPS.md`](GAPS.md) — current, actively-maintained audit of what's built, partially built, and still open
- [`GAME_DESIGN.md`](GAME_DESIGN.md) — world, characters, the World Bank skills framework the badge/achievement system is built on, B1llbot's voice and system prompt
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — the original target-state technical architecture and the reasoning behind it (largely executed at this point — treat as historical/rationale, defer to `GAPS.md` for current status)
- [`BUILD_PLAN.md`](BUILD_PLAN.md) — the build spec this pass worked from (custom Minecraft container, missions synced from the Brightspace sim, event catalog, profiles)
- [`UI_SPEC.md`](UI_SPEC.md) — the gamified web experience: mission loop, profile pages, Companion Mode, and the wireframe skinning contract
- [`UX_HANDOFF.md`](UX_HANDOFF.md) — handoff doc for a UX designer restyling the app (which files are safe to edit, how to run it)
- [`HOSTING_COST_MODEL.md`](HOSTING_COST_MODEL.md) — per-cohort AWS sizing/cost framework for real deployment
- [`docs/README.md`](docs/README.md) — index of narrative/curriculum docs, split into `canon/` (current source of truth), `legacy/` (superseded drafts), and `process/` (meeting notes, planning chats)

## Status

Read [`GAPS.md`](GAPS.md) for the real, current picture — it's updated after every build pass and is more trustworthy than a prose summary here would stay. In short: the 12-mission curriculum, teams, XP/levels with named Agent ranks, the 4 Superpower badges plus their 16 constituent Powers, a peer-interaction gallery, a class-wide activity feed, mission release gating, a Minecraft connect flow, and B1llbot (both web chat via OpenWebUI and, when its mod is buildable again, in-game) are real and working end to end.

Also real as of the latest pass: **"The Water Rises"** collective world-state (the whole cohort's mission completions advance Keel through 9 restoration stages — on the Hub, in the class feed, and physically in the Minecraft world as a growing Restoration Beacon plus full-screen in-game celebrations), a **live WebSocket layer** (the Hub updates in real time; classmates' awards and rank-ups arrive as toasts; your own level-up is a full-screen moment on web *and* in-game), **live Basin presence** ("who's in Minecraft right now" on the Hub and phone), **Training Sims** (two curriculum-bearing browser minigames at `#/arcade` with leaderboards and capped XP), a hidden **Alchemy Signal** scavenger hunt, an **Agent Dossier** profile, an installable **Field Kit** phone PWA (scan the QR on the Hub), and the production visual skin ported from `ui/Final Prosperity Showcase.html`. `GAPS.md`'s own "five that matter most" section names the highest-leverage remaining gaps.
