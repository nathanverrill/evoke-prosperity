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

Minecraft (optional, Prosperity-specific) comes up as part of `evoke-infra`. See `evoke-infra/minecraft/world-seed/README.md` for loading the real Basin Simulation world instead of a fresh vanilla one. In dev, the first real player to connect gets auto-linked to Player One — no setup needed to see rewards, XP, and B1llbot lore arrive in-game. Real per-learner linking is the two-channel flow: scan the Hub QR to pair your phone, tap **Connect to Basin Simulation**, and type the shown `/trigger evoke_link set <code>` in-game — full walkthrough at `#/faq`.

---

## Repo layout

```
evoke/          FastAPI backend + vanilla-JS SPA — see evoke/main.py, workers.py, clients.py, static/
evoke-infra/    Shared infrastructure: Postgres, MinIO, Redpanda, OpenSearch, OpenWebUI, Ollama, Minecraft (docker-compose)
brightspace-sim/ Brightspace LMS simulator (real Brightspace API shapes) -- system of record for the 12 missions in dev
evoke-minecraft-bridge/ Real-RCON bridge: reward delivery, world-stage celebrations + Restoration Beacon, presence, scoreboard quest-triggers, /trigger link codes, heartbeat
ui/             "Final Prosperity Showcase.html" -- the approved visual reference; the live skin was ported from it
docs/           Narrative, curriculum, and planning source material -- see docs/README.md
scripts/        Deployment/setup shell scripts, plus minecraft-world-tools/ -- stdlib-only NBT/Anvil tools for reading the real Minecraft world save directly
```

- [`CONCEPTS.md`](CONCEPTS.md) — glossary and orientation (start here)
- [`GAPS.md`](GAPS.md) — current, actively-maintained audit of what's built, partially built, and still open
- [`GAME_DESIGN.md`](GAME_DESIGN.md) — world, characters, the World Bank skills framework the badge/achievement system is built on, B1llbot's voice and system prompt
- [`MINECRAFT_WORLD_MAP.md`](MINECRAFT_WORLD_MAP.md) — what's *actually built* in the real `basin` world save (minigames, secrets, economy, kiosk) — found by directly parsing the world files, not from any design doc
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — the original target-state technical architecture and the reasoning behind it (largely executed at this point — treat as historical/rationale, defer to `GAPS.md` for current status)
- [`BUILD_PLAN.md`](BUILD_PLAN.md) — the build spec this pass worked from (custom Minecraft container, missions synced from the Brightspace sim, event catalog, profiles)
- [`UI_SPEC.md`](UI_SPEC.md) — the gamified web experience: mission loop, profile pages, Companion Mode, and the wireframe skinning contract
- [`UX_HANDOFF.md`](UX_HANDOFF.md) — handoff doc for a UX designer restyling the app (which files are safe to edit, how to run it)
- [`HOSTING_COST_MODEL.md`](HOSTING_COST_MODEL.md) — per-cohort AWS sizing/cost framework for real deployment
- [`SAFETY.md`](SAFETY.md) — code of conduct, COPPA/FERPA posture, and an AI-reject/human-approve content moderation model — a real policy draft, explicitly not a substitute for legal counsel
- [`COMPLIANCE_TODO.md`](COMPLIANCE_TODO.md) — sequenced P0/P1/P2 compliance action list for a real Colorado pilot
- [`WHITELIST.md`](WHITELIST.md) — confirmed (not hypothetical) evidence the Minecraft server has been reached by non-project entities, who's verified and cleared to whitelist, and the server-config changes required to close the exposure
- [`GUARDRAILS_PLAN.md`](GUARDRAILS_PLAN.md) — AI gateway build spec (LiteLLM + Presidio + content filter) in front of every real AI call site; Phase 0/1 is live
- [`docs/README.md`](docs/README.md) — index of narrative/curriculum docs, split into `canon/` (current source of truth), `legacy/` (superseded drafts), and `process/` (meeting notes, planning chats)

## Status

Read [`GAPS.md`](GAPS.md) for the real, current picture — it's updated after every build pass and is more trustworthy than a prose summary here would stay. In short: the 12-mission curriculum, teams, XP/levels with named Agent ranks, the 4 Superpower badges plus their 16 constituent Powers, a peer-interaction gallery, a class-wide activity feed, mission release gating, a Minecraft connect flow, and B1llbot (both web chat via OpenWebUI and, when its mod is buildable again, in-game) are real and working end to end.

Also real as of the July 2026 build passes: **"The Water Rises"** collective world-state (the cohort's completions advance Keel through 9 stages — on the web, in the feed, and physically in Minecraft as a growing Restoration Beacon), the **Campaign Map** at `#/map` (the "what done means" infographic: instructor-configured stages, completion rings, ★–★★★ quality grades that resubmission raises), a **live WebSocket layer** (real-time feed, toasts, full-screen level-ups on web *and* in-game), **live Basin presence**, **Training Sims** (`#/arcade`), the daily **Field Report / Words of Wisdom** (reflections to B1llbot, collected in a Wisdom Journal; 10 unlock the Transformation Power), an **Agent Dossier** profile (sigil/photo avatars, combo-unlocked Field Gear, the Aqueduct Kit collectible), a hidden **Alchemy Signal** hunt, an installable **Field Kit** phone PWA (the Hub QR pairs your phone with no login, and now self-corrects to your machine's real LAN IP even if you opened the app via localhost), **two-channel Minecraft linking** (`/trigger evoke_link set <code>` in-game + confirm on your phone — instructions inline and at `#/faq`), **scoreboard-driven quest auto-completion** (the world reports itself), the **Team Wheel**, an **Instructor Ops Deck** at `#/admin`, and the production skin ported from `ui/Final Prosperity Showcase.html`. `GAPS.md`'s own "five that matter most" section names the highest-leverage remaining gaps.

Also real as of the 2026-07-16 build pass: mission completion is genuinely **team-centric** now, matching the real curriculum content — a team's evidence is one shared artifact any member can submit, and each learner separately submits their own **reflection** (personal, required to earn their own award/XP). Every mission shows its real "Your Mission" narrative (Step 1/2/3 structure) and an Evidence checklist, not just a one-line summary. The Minecraft side also got a robustness pass this same window — see `MINECRAFT_WORLD_MAP.md` for the in-world minigames (a couple had real bugs, like a free-money exploit in the coinflip room, found and fixed) and a newly-recovered co-op arena, **the Mob Gauntlet**.

Also real as of the 2026-07-19 build pass: **auth is no longer dev-grade.** A real, swappable **OAuth 2.0 login** (`AUTH_PROVIDER`, Brightspace is the first implementation — "Login with Central Registry" in-fiction) replaces auto-signing everyone in as Player One whenever a real provider is configured; team assignment now syncs automatically from **Brightspace's own Groups feature** instead of a manual admin step; and every route depends on a **real, signed session cookie** for "who's calling" instead of trusting a client-supplied `user_id` — verified live that this actually blocks cross-user access (403), not just documents that it should. A persistent **agent-account widget** (real name from Brightspace, formatted `LASTNAME//FIRSTNAME`) plus Log Out is visible on every screen now. The old `#/admin` roster-import/team-assignment UI is gone — it was only ever reachable through dead code anyway — replaced by the Groups sync above, plus a new `POST /api/admin/login` (disabled until `scripts/hash_admin_password.py` sets a real password) for the one non-Brightspace identity: reaching `#/admin` itself. Separately, a standalone test harness (`evoke/static/test-brightspace.html`) confirmed pulling real assignments and submitting real coursework are both technically reachable against a real Brightspace tenant — not yet wired into the production mission catalog, since a real Brightspace assignment has no field for Evoke's curriculum metadata (arc, superpower, skills, PFL domain). All of this currently lives on the `dev` branch, pushed to `origin/dev`, not yet merged to `main`.
