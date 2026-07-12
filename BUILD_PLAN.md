# BUILD_PLAN.md — EVOKE Prosperity, current build

**This is the active build spec.** It supersedes every doc in `docs/build-history/` (the July 2026 sprint docs). It assumes you've read [`CONCEPTS.md`](CONCEPTS.md) and [`ARCHITECTURE.md`](ARCHITECTURE.md) — those remain the orientation map and target-state architecture. The UI companion to this doc is [`UI_SPEC.md`](UI_SPEC.md).

**What changed since the last spec:** the July sprint built most of the plumbing (Brightspace sim, LTI 1.3, LMS adapter, Minecraft RCON bridge, awards/collect pipeline, Postgres schema, seed script). This build hardens and reshapes it around five directives:

1. **Custom Minecraft container** — replace `itzg/minecraft-server` with our own image built from a Dockerfile in this repo.
2. **Reliable bring-up** — `evoke-infra` then `evoke` come up cleanly with `docker compose up -d`, every service health-checked, no manual steps. Compose project name is `evoke` (not `evoke-app`).
3. **Gamified web experience** — Urgent-Evoke-style mission loop (graphic novel → mission → completion → operations hub), wireframe-styled for a UX designer to skin later. Team profile and player profile pages showing progress, badges, missions completed, and quests completed.
4. **Missions come from the Brightspace simulator** — the sim is the system of record for assignments; EVOKE syncs its mission catalog from it, exactly as it will from real Brightspace.
5. **Everything event-based on Redpanda** — every state change in the learner experience is an event on `evoke-events`; the web app, profiles, Minecraft bridge, and LMS sync are all consumers/projections of the same stream.

---

## Reuse map — what exists and what happens to it

Built in July, verified working (see `docs/build-history/PROJECT_COMPLETION_SUMMARY.md` for the full inventory):

| Component | Location | Disposition |
|---|---|---|
| Brightspace API simulator | `brightspace-sim/` (FastAPI: OAuth 2.0, whoami, Dropbox, Award Service, Groups, teacher review UI) | **Keep, extend** — becomes the mission source of record (below) and gets an accuracy pass against real D2L API shapes |
| LTI 1.3 provider | `evoke/lti/brightspace_lti_provider.py` (JWT verify, auto-provisioning, sessions) | **Keep as-is** |
| BrightspaceLMS adapter | `evoke/lms/brightspace_lms.py` (OAuth service account, submit/badge/grade sync) | **Keep as-is** — sim vs. real is a config change |
| Event pipeline | `evoke/main.py`, `workers.py`, `clients.py` (submit → Redpanda → AI/timeline workers → OpenSearch) | **Keep, extend** with the new events below |
| Minecraft reward bridge | `evoke-minecraft-bridge/bridge.py`, `evoke/minecraft/` (RCON client, tier rewards) | **Keep** — repoint at the custom Minecraft container; verify it consumes `RewardCollected`, not `AwardGranted` (collect-gate rule, below) |
| Postgres schema + seed | `evoke-infra/init-db.sql`, `evoke-infra/seed.py` | **Keep, extend** for quests/profiles/teams |
| Companion mode | `evoke/static/companion.html` | **Keep** — restyle per `UI_SPEC.md` wireframe tokens |
| Main SPA | `evoke/static/index.html` | **Replace** with the mission-loop UI in `UI_SPEC.md` (current page is the old pipeline-demo wireframe) |
| Minecraft server | `itzg/minecraft-server` image in `evoke-infra/docker-compose.yml` | **Replace** with the custom container (below) |
| Polished mockup | `ui/Final Prosperity Showcase.html` | **Reference only** — design target for the mission loop; not wired to anything |
| Basin Simulation world + datapacks + B1llbot Fabric mod + lore KBs | `~/evoke-prosperity-files/` (outside the repo) | **Migrate in** — becomes the content of the custom Minecraft container (below); `kbs/*.md` seed the OpenWebUI B1llbot knowledge base |

---

## Topology

Two compose stacks, same as today, project name `evoke`:

- **`evoke-infra/`** — postgres, redpanda (+console), opensearch (+dashboards), minio, open-webui, **minecraft (custom image)**. Shared network `evoke-infra-network`.
- **`evoke/`** — `web` (the EVOKE FastAPI app), `brightspace-sim`, `minecraft-bridge`. Joins the infra network.

Bring-up contract (this is directive #2, treat as acceptance criteria):

- `cd evoke-infra && docker compose up -d` → every service reaches `healthy` with no manual intervention; postgres runs `init-db.sql` + seed on first boot.
- `cd evoke && docker compose up -d --build` → `web` waits on infra health (compose `depends_on`/retry in app startup, as today), `brightspace-sim` self-seeds its 12 assignments, bridge connects RCON with retry.
- Every service exposes `/health` (or the container equivalent) and has a compose healthcheck. `docker compose ps` showing all-healthy is the smoke test.

---

## Custom Minecraft container (directive #1)

**Hard requirement: Java Edition server modified to accept Bedrock clients.** Students will connect from both Java and Bedrock (phones/tablets/consoles/school devices), so the server ships with **GeyserMC + Floodgate** — Geyser translates the Bedrock protocol to Java, Floodgate lets Bedrock players join without a paid Java account. This resolves the Java-vs-Bedrock question that was previously flagged as the #1 risk in `GAPS.md`.

**The server is Fabric, not Paper.** Substantial Minecraft work already exists in `~/evoke-prosperity-files/` (currently outside this repo — migrating it in is part of this build):

```
evoke-prosperity-files/minecraft/
  minecraft-world-files/true_oasis/      the custom Basin Simulation world (command
                                          blocks, scripts, embedded datapacks)
  minecraft-world-files/unmodded/         unmodded fallback variant of true_oasis
  minecraft-world-files/wil-world/        second world (overworld/nether/end)
  billbot_and_lore/kbs/                   OpenWebUI knowledge bases: keel.md,
                                          alpha_dynamics.md, lore.md
  billbot_and_lore/datapacks/             narrative/economy datapacks: halyard_rent_functions,
                                          mines_lift_precheck, custom_drops, inventory_save
  billbot_simple_chat_plugins/billbot/    B1llbot in-game chat — a built Fabric mod
                                          (billbot-1.0.1.jar)
```

The B1llbot chat mod being Fabric dictates the server flavor, and it supersedes `ARCHITECTURE.md`'s "no custom plugin, log-tail only" decision — the mod is built and working; use it.

Container shape — replace `image: itzg/minecraft-server` with `build: ./minecraft` in `evoke-infra/`:

```
evoke-infra/minecraft/
  Dockerfile          # FROM eclipse-temurin:21-jre; pinned Minecraft + Fabric
                      # loader versions as build args; non-root user
  entrypoint.sh       # templates server.properties from env (RCON_PASSWORD, ports,
                      # motd), accepts EULA via env, execs the server
  server.properties.template
  mods/               # billbot-<ver>.jar, Geyser-Fabric, Floodgate — version-pinned
  datapacks/          # halyard_rent_functions, mines_lift_precheck, custom_drops,
                      # inventory_save (from evoke-prosperity-files)
  world-seed/         # true_oasis world — copied to the volume on first boot only
```

Requirements:

- **Pinned versions everywhere** — Minecraft, Fabric loader, each mod jar. Upgrades are a deliberate diff, and Geyser/Bedrock compatibility is version-sensitive.
- **Bedrock ingress** — expose UDP 19132 (Geyser) alongside TCP 25565; verify a Bedrock client and a Java client can share the world as part of bring-up acceptance.
- **RCON enabled** — same env contract the bridge already uses (`RCON_PASSWORD` from `.env`, port 25575). The bridge must not need code changes to point at the new container.
- **Health check** — probe RCON `list` (or the server port), so `depends_on: condition: service_healthy` works for the bridge.
- **Persistent world** — named volume; `world-seed/` copies in only when the volume is empty, so restarts and image rebuilds never wipe a live world. Keep the `unmodded` variant available as a recovery/reset option.
- **B1llbot mod wiring** — the Fabric mod's OpenWebUI endpoint/model key comes from env (`OPENWEBUI_BASE_URL`, `AI_COACH_MODEL`), matching the web app, and the `kbs/` markdown files are loaded into OpenWebUI's B1llbot knowledge base by the bootstrap script (see GAPS — automating OpenWebUI setup).
- **Floodgate identity note** — Bedrock players arrive with Floodgate-prefixed usernames (default `.`-prefix) and Floodgate UUIDs; the reward bridge's username matching and `minecraft_links` linking flow must handle both identity shapes. Test the collect→RCON delivery path with a Bedrock player explicitly.
- **Why custom instead of itzg**: full control of version pinning, baking in the mods + world + datapacks as *content in this repo*, and a smaller surface than itzg's mod-manager machinery.

---

## Missions come from the Brightspace sim (directive #4)

**The LMS is the system of record for missions.** This inverts the July build (which seeded missions into EVOKE's Postgres and pushed submissions to the sim):

1. `brightspace-sim` self-seeds the 12 Prosperity missions as **real Brightspace-shaped assignments** (Dropbox folders) in its in-memory store, with EVOKE's mission metadata (arc, superpower, PFL domain, brief, narrative copy) carried in the assignment's custom fields/description exactly where real Brightspace would carry them.
2. On startup (and on a periodic/refresh trigger), the EVOKE app **pulls the assignment list** through the `LMSSync` adapter and upserts its `missions` table — Postgres becomes a synced cache keyed by `lms_assignment_ref`, not an independent catalog. `evoke-infra/seed.py` stops seeding missions; it keeps seeding users, teams, quests, and the reward catalog (EVOKE-native content the LMS doesn't own).
3. Submitting evidence stays what it already is: a real Dropbox submission to the sim + a MinIO copy for the AI worker + events on Redpanda.
4. Teacher grading stays in the sim's review UI (standing in for the Brightspace gradebook) → webhook → `TeacherReviewed` event → award tier.

**Why:** with the customer's real Brightspace, missions will be authored as course assignments by instructional designers — EVOKE must consume them, not own them. Making the sim work this way now means the cutover is credentials + base URL, not a data-flow rewrite.

### Sim accuracy checklist (easing the real-Brightspace transition)

The sim must mirror real D2L shapes closely enough that `BrightspaceLMS` cannot tell the difference:

- Route shapes: `/d2l/api/lp/{version}/users/whoami`, `/d2l/api/le/{version}/{orgUnitId}/dropbox/folders/…`, `/d2l/api/bas/{version}/orgunits/{orgUnitId}/issued/`, OAuth 2.0 `POST /core/connect/token` client-credentials flow — field names and casing per real payloads (research in `docs/process/thread3.md`).
- LTI 1.3 launch: real claim URIs (`https://purl.imsglobal.org/spec/lti/claim/…`), RS256, JWKS endpoint the app fetches keys from — no sim-only shortcuts in the app's verify path.
- Pagination/error envelopes where EVOKE reads lists (assignment list, submissions) — match D2L's `PagedResultSet` shape.
- Anything knowingly divergent gets a `# SIM-DIVERGENCE:` comment at the divergence site plus a line in `brightspace-sim/README.md`, so the real-integration punch list writes itself.

---

## Event catalog (directive #5)

One topic, `evoke-events`, as today. Full catalog for this build — anything that changes learner-visible state must be one of these, and profiles/timeline/bridge/LMS-sync are all just consumers:

```
EvidenceSubmitted        learner submits mission evidence (→ dropbox + MinIO copy)
AwardGranted             tier award created (common on submit; epic on AI pass;
                         epic|legendary on teacher review) — inserts awards + notifications
FeedbackGenerated        AI Coach structured judgment {consistent, feedback}
TeacherReviewed          sim/Brightspace webhook landed with a grade
RewardCollected          learner clicked Collect — the ONLY event the Minecraft
                         bridge delivers on (collect-gate rule, unchanged)
MissionCompleted         mission reaches completed state (grade synced)
QuestCompleted           player self-reports a Minecraft side quest done (with
                         optional observation text + screenshot) — feeds profiles
                         ONLY; never touches Brightspace or the award pipeline
XPGranted                XP ledger event (submission, collection, quest — additive only)
BadgeAwarded             a Superpower badge earned (mission-completion driven);
                         consumed by the LMS-sync worker → Award Service, and by
                         profile projections
TeamEvidenceSubmitted    team-scoped submission (venture missions, weeks 4–6)
```

Projections (OpenSearch, built by `workers.py` consumers): `learner-timeline` (as today), **`player-profile`** and **`team-profile`** (new — see `UI_SPEC.md` for the read shapes), `instructor-dashboard`. Profile pages render projections only; they never compute progress by querying Postgres tables at request time. Idempotency per `(user_id, mission_id, tier, source)` for awards, per `(user_id, quest_id)` for quest completions.

### Award mechanics (carried forward from the July build — these rules are load-bearing)

- **The award ladder** comes entirely from the LMS submission pipeline: submitting evidence grants **common** (`source=submission`); an AI pass grants **epic** (`source=ai_review`); teacher review grants **epic or legendary** (`source=teacher_review`, by grade tier). Minecraft play never affects tiers.
- **The collect gate**: `awards.collected_at` is null until the learner actively clicks Collect (main site or Companion Mode). Only then does `RewardCollected` fire, and that is the only event the Minecraft bridge delivers on. Delivering on `AwardGranted` breaks the product intent — the learner must come to the website to claim. Offline-safe: uncollected deliveries retry when the player next logs in (`mc_reward_grants` pending loop).
- **AI structured judgment**: the AI Coach returns `{"consistent": true|false, "feedback": "..."}` — `consistent: true` is what triggers the epic award, prose feedback becomes an Insight either way. With `AI_ENABLED=false`, the AI award step is skipped entirely; common + teacher paths still work.
- **"Evidence" means two unrelated things** — never share a table or pipeline: *mission evidence* is a real LMS Dropbox submission that feeds the award pipeline; *quest evidence* (observation text + screenshot on a self-report) is a personal field log that feeds only profiles.

**Quests, precisely:** a *quest* is a Minecraft side activity (kind `side_quest`, plus one thematic `mission_quest` per mission), **self-reported by the player** from the web app or Companion Mode ("I did this" + optional observation/screenshot). Self-reporting emits `QuestCompleted`, which shows up on player and team profiles and can grant XP — but per canon (`docs/canon/thread5.md`) it never gates a mission, never reaches the LMS, and never triggers tier awards.

---

## Team & player profiles (directive #3, data side — UI in `UI_SPEC.md`)

- **Player profile** — identity (display name, linked Minecraft username), XP/level, streak, badges earned (the four Superpowers with earned/progress state), missions completed (n of 12, by arc), quests completed (count + list with self-reported observations), award history with collected state.
- **Team profile** — team name/members (with `role_label`), aggregate mission progress (team missions completed), combined badge wall, team quest count, and later Venture Points allocation (schema exists per `ARCHITECTURE.md`; UI in week-4+ missions).
- Postgres additions: none — `init-db.sql` already defines the needed tables (`awards`, `mc_quests`, `mc_quest_completions`, `mc_quest_submissions`, `teams`, `team_members`); the new work is the two OpenSearch profile projections and their API reads:

```
GET /api/profile/player/{user_id}     → player-profile projection
GET /api/profile/team/{team_id}      → team-profile projection
POST /api/mc-quests/{quest_id}/submit → self-report (emits QuestCompleted)
```

---

## Acceptance scenario

Done means, on localhost, with real events on Redpanda:

1. Both stacks come up healthy from scratch (`docker compose up -d` twice, nothing else), Minecraft served by the custom image.
2. Missions visible in EVOKE are the ones pulled from `brightspace-sim`'s assignment store — delete one in the sim's admin, refresh sync, it disappears from EVOKE.
3. Learner runs the full mission loop in the new UI: graphic-novel panel → mission brief → evidence submit → common award notification → (AI pass) epic award → teacher grades in the sim review screen → third award.
4. Learner collects awards (main site or Companion Mode) → rewards arrive in the custom Minecraft container via RCON, offline-safe.
5. Learner self-reports a side quest with an observation + screenshot → `QuestCompleted` on the topic → it appears on their player profile and their team's profile; nothing appears in the sim's gradebook.
6. Player profile and team profile pages render entirely from OpenSearch projections and show: badges, missions completed, quests completed, XP/level, awards.
7. Kill and restart `web` mid-flow: no double awards, no lost events (idempotent consumers).
8. `AI_ENABLED=false` still yields the common + teacher-review award path.
9. B1llbot answers in character from the main site, Companion Mode, and in-game via the Fabric chat mod — all three through the same OpenWebUI custom model.
10. A Bedrock client (via Geyser/Floodgate) and a Java client both join the Basin Simulation world, and a Bedrock-linked learner receives a collected reward via the bridge.

---

## Build order

**Status checklist** — verified against the actual code, not assumed from this plan. Re-check by grepping the specific evidence noted before trusting a ✅ that's more than a few sessions old.

1. ✅ **Compose hardening** — healthchecks added to `web`/`brightspace-sim`/`minecraft-bridge` (verified against real builds + a real throwaway Postgres, `docker ps` confirmed "healthy"). That verification surfaced and fixed two pre-existing bugs that crashed every boot regardless of healthchecks: `evoke/Dockerfile` flattened the `evoke` package into `/app` when `main.py` imports it as `evoke.X`, and `brightspace-sim`'s Dockerfile was missing `python-multipart` (its Form() endpoints need it to boot at all). Project name `evoke` and `.env.example` were already done.
2. ✅ **Custom Minecraft container** — replaces `itzg/minecraft-server`, built and verified end-to-end (not just written): image builds, server boots (`Done (1.975s)!`), all four mods load (BillBot v1.0.1, Floodgate, Geyser on UDP 19132), all four datapacks load with no errors, real RCON auth + `list` command both succeeded against the running server. Found and fixed two real version-compatibility bugs by actually running it: Fabric Loader needed bumping from the mod's own 0.16.10 pin to 0.19.3 (current Fabric API/Geyser-Fabric builds require >=0.17.x; safe since the mod doesn't hard-pin an exact loader version), and two of the four datapacks silently failed to load on a `pack_format: 88` declaration missing fields MC 1.21.10 now requires above format 81 — lowered to `pack_format: 48` to match the two datapacks that already worked. **Deliberately not done:** the real ~704MB `true_oasis` world isn't committed — see `evoke-infra/minecraft/world-seed/README.md` for the three real options (git-lfs / S3-at-build / manual placement); the container is fully functional and falls back to vanilla world generation until that's decided.
3. ⚠️ **Missions-from-sim inversion** — *not done.* `evoke-infra/seed.py` still seeds all 12 missions directly into Postgres (with an `lms_assignment_ref` column already present, so the schema anticipates the inversion — it just isn't wired). `evoke/lms/brightspace_lms.py` is used one-directionally today (`push_badge_award`, pushing *to* Brightspace) — nothing pulls the mission catalog *from* the sim on startup yet.
4. ⚠️ **Event catalog completion** — *partial.* `EvidenceSubmitted`/`AwardGranted`/`RewardCollected` all emit correctly. `QuestCompleted`, `XPGranted`, `MissionCompleted`, `BadgeAwarded` don't exist anywhere in `main.py`. `/api/mc-quests` and `/api/mc-quests/{quest_id}/submit` **exist and work**, but the submit path doesn't emit `QuestCompleted` — quests are recorded with nothing downstream. `player-profile`/`team-profile` OpenSearch projections and their read APIs don't exist.
5. ❌ **Gamified web app** — *not done.* `evoke/static/index.html` is still the original pipeline-demo page (a "Dev Login" button, a bare missions list, a notifications list) — not the mission-loop SPA specified in `UI_SPEC.md`. Blocked on #4's profile APIs to have real data to render.
6. ❌ **End-to-end pass** — blocked on the above.

## Non-goals (this pass)

- No real Brightspace connection (sim only — but sim accuracy is in scope).
- No visual polish — wireframe tokens only; the UX designer skins it (see `UI_SPEC.md` for the skinning contract).
- No *new* Minecraft mods beyond what exists (B1llbot chat mod, Geyser, Floodgate); reward delivery stays RCON + vanilla commands.
- No multi-org/multi-campaign runtime; schema stays campaign-scoped as designed.
- No UUID-based Minecraft linking upgrade (username-match stays, per `ARCHITECTURE.md` MVP note).
