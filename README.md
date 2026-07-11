# EVOKE Prosperity

A mission-based learning platform for teaching financial literacy and entrepreneurship, wrapped in a transmedia narrative (graphic novel + web app + optional Minecraft). Students complete real-world "missions" that are presented back to them as an unfolding story rather than assignments.

**New to this repo?** Read [`CONCEPTS.md`](CONCEPTS.md) first — it's a glossary and orientation map (story terms, curriculum terms, canon vs. legacy docs, repo layout) written for anyone or any AI assistant picking this up cold.

---

## Quickstart

Start infrastructure:

```
cd evoke-infra
docker compose up -d
```

Start the app:

```
cd evoke
docker compose up -d --build
```

Then go to [http://localhost:8000](http://localhost:8000).

AI feedback is optional and off by default (`AI_ENABLED=false` in [`evoke/docker-compose.yml`](evoke/docker-compose.yml)). To enable it, point `OLLAMA_BASE_URL` at a local Ollama instance (or any OpenAI-compatible endpoint) and set `AI_ENABLED=true`.

---

## Repo layout

```
evoke/          FastAPI backend (current running prototype) — see evoke/main.py, workers.py, clients.py
evoke-infra/    Shared infrastructure: MinIO, Redpanda, OpenSearch, Keycloak (docker-compose)
ui/             Polished interactive UI mockup — design target, not yet wired to the backend
docs/           Narrative, curriculum, and planning source material — see docs/README.md
```

- [`CONCEPTS.md`](CONCEPTS.md) — glossary and orientation (start here)
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — target-state technical architecture and the reasoning behind it
- [`BUILD_PLAN.md`](BUILD_PLAN.md) — the active build spec (custom Minecraft container, missions synced from the Brightspace sim, event catalog, profiles)
- [`UI_SPEC.md`](UI_SPEC.md) — the gamified web experience: mission loop, profile pages, Companion Mode, and the wireframe skinning contract
- [`docs/README.md`](docs/README.md) — index of narrative/curriculum docs, split into `canon/` (current source of truth), `legacy/` (superseded drafts), and `process/` (meeting notes, planning chats)

## Status

This is an early-stage prototype. The backend proves the core event pipeline (evidence submission → AI/instructor feedback → learner timeline) with a single hardcoded demo mission; the curriculum, identity/teams, and most of the UI mockup's features (XP, badges, Vault, Profile) are not yet wired up. See `CONCEPTS.md`'s "Known gaps / traps for agents" section for specifics.
