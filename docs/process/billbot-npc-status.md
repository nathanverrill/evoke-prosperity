# Billbot NPC system — status as of 2026-07-17

What's live on `prosperity` (Apex, `6689.node.apexhosting.gdn`) right now, how it
got there, and what's intentionally on hold. Written for whoever (human or
agent) picks this up next.

## TL;DR current state

- **Only Billbot is active.** Jim, Beth, Benjamin, and Craig were pulled out
  today at the user's request ("just have Billbot, we'll add the others back
  later"). Their full character prompts/locations are still in git history —
  see "Bringing the other 4 back" below.
- Billbot is a **copper golem**, not the iron golem he started as today.
- Chat works via proximity (stand near him, no `@` prefix needed) or `@billbot`
  from anywhere, routed through OpenWebUI's `billbot` custom model
  (`gpt-4.1-nano` base).
- There's exactly **one pressure plate** at his kiosk now (was three).

## Why a chat-only mod instead of ThirdBrain

The project used to use ThirdBrain (a third-party Fabric mod) for NPC chat via
fake-player entities with skins. It was fragile (alpha-quality, version-locked
to old Fabric mappings) and its fake-player approach doesn't survive a
Minecraft version bump cleanly. We rebuilt NPC chat as a from-scratch feature
in the team's own `billbot.jar` mod instead:

- **Chat logic and visual presence are decoupled on purpose.** The mod
  (`BillBot.java`) only handles chat — it doesn't summon or require any
  entity at all. A *separate* datapack (`keel_npcs`) summons the visible
  body. This means chat can never break because of an entity-spawning bug,
  and vice versa.
- We checked: 26.2 mappings (Yarn and Mojang both) don't exist yet, so any
  fresh Fabric mod compile is pinned to `1.21.11` for now, same as the rest
  of the server.

## Architecture

```
billbot.jar (Fabric mod, source: ~/evoke-prosperity-files/minecraft/billbot_simple_chat_plugins/billbot/)
  reads config/billbot/npcs.json at boot (once — no hot reload)
  listens on ServerMessageEvents.ALLOW_CHAT_MESSAGE
  matches "@name" prefix, or nearest NPC within its `range` if no prefix
  → POSTs to OpenWebUI (ngrok tunnel) with the NPC's `character` as system prompt
  → replies in chat

keel_npcs datapack (evoke-infra/minecraft/datapacks/keel_npcs/)
  #minecraft:load → summons the visible NPC body/bodies
  tag-checked (idempotent) so a restart never re-summons duplicates
  purely cosmetic -- has zero knowledge of chat, just a body to stand near
```

These two systems only agree by convention: **an NPC's `x/y/z` in
`npcs.json` should match its summon coordinates in `keel_npcs`**, so standing
next to the visible body actually puts you in chat range. Nothing enforces
this automatically — if you move one, move the other.

## Billbot's entity: copper golem, waxed, invulnerable

Adventure mode blocks block breaking/placing but **does not block attacking
entities** — this bit us today. The original iron golem got punched to death
by a player testing the kiosk. Went through the options:

| Option | Verdict |
|---|---|
| Iron golem + `Invulnerable:1b` | Works, but combat-coded design (idle/attack animations) even when neutered |
| Armor stand | Zero combat behavior, but no real "robot" silhouette without manual assembly |
| **Copper golem** (chosen) | Passive by vanilla design (its whole purpose is sorting items between chests, not fighting) — more "mechanism," less "guardian." Added in Java 1.21.9, so it exists on this server's 1.21.11. |

Current live summon command (`keel_npcs/data/keel_npcs/function/load.mcfunction`):

```mcfunction
execute unless entity @e[type=copper_golem,tag=keel_npc_billbot] run summon copper_golem -49 65 208 {Tags:["keel_npc_billbot"],CustomName:'{"text":"Billbot"}',CustomNameVisible:1b,PersistenceRequired:1b,Silent:1b,NoAI:1b,Invulnerable:1b,weather_state:unaffected,next_weather_age:-2}
```

- `Invulnerable:1b` — can't be killed regardless of gamemode.
- `NoAI:1b` — no wandering, no AI-driven behavior.
- `weather_state:unaffected,next_weather_age:-2` — **permanently waxed**.
  Copper golems normally oxidize over ~7-7.5 hours into a frozen statue pose;
  `next_weather_age:-2` is the NBT value that means "waxed, will never
  oxidize." Without this he'd visually freeze mid-playtest.

## Known cosmetic bug (unresolved): nameplate shows raw JSON

At least once, a player reported seeing the literal text `{"text":"Billbot"}`
above his head instead of just "Billbot". The NBT itself is correct — this is
the standard, correct JSON text-component format for `CustomName`, confirmed
via `data get entity`. Suspected cause: **Geyser's Bedrock translation layer
may not yet know how to render/parse `CustomName` for entity types added as
recently as the copper golem** (Java 1.21.9), especially since the server's
pinned Geyser build may predate that mob's addition. Not yet confirmed
whether this also affects the villager NPCs on a Java client vs. Bedrock —
if you hit this again, the first diagnostic question is **which client
(Java or Bedrock via Geyser) and does it affect all NPCs or just the copper
golem specifically.**

If it turns out to be a hard Geyser limitation, the fallback is switching
Billbot back to iron golem (well-supported, ordinary mob) or an armor stand.

## Model routing (why some NPCs used to time out)

- `npcs.json`'s `model` field is sent directly in the API request. Sending
  `"model":"qwen3:8b"` bypasses OpenWebUI's `billbot` custom-model wrapper
  entirely (system prompt, RAG knowledge base, whatever base model is
  configured for it).
- `qwen3:8b` running its "thinking"/reasoning mode routinely takes ~30s,
  right at the mod's client-side HTTP timeout — this caused real, reproduced
  timeouts (confirmed via Apex server logs).
- Fix applied today: Billbot's `model` is `"billbot"` (the OpenWebUI custom
  model, `gpt-4.1-nano` base, ~1.6-2.6s response time, no reasoning-token
  issue). When Jim/Beth/Benjamin/Craig come back, point them at
  `"gpt-4.1-nano"` directly too (confirmed via curl this works as a raw,
  directly-selectable model ID in this OpenWebUI instance, no need to build
  4 more custom wrapper models).

## Deployment mechanics (Apex FTP + RCON)

No CI/CD — file changes require manual FTP upload, config/datapack changes
require an RCON-triggered restart (the mod only reads `npcs.json` once, at
boot).

- **FTP**: host `6689.node.apexhosting.gdn`, port 21, username
  `nathanverrill@gmail.com.3277476` (this server instance's unique FTP user —
  every Apex server instance has its own). Password is the Apex account
  password (not stored in any repo file — get it from whoever has it).
- **Real paths on the FTP server** (note the `default/` prefix — easy to
  miss):
  - `default/config/billbot/npcs.json`
  - `default/basin/datapacks/keel_npcs/data/keel_npcs/function/load.mcfunction`
    (`basin` is this server's `level-name`, confirmed via `server.properties`)
- **RCON**: host/port/password in root `.env`
  (`MINECRAFT_BRIDGE_HOST` / `MINECRAFT_BRIDGE_RCON_PORT` /
  `MINECRAFT_BRIDGE_RCON_PASSWORD`). Client: `evoke/minecraft/rcon_client.py`
  (hand-rolled async RCON protocol implementation).
- **Restart to apply a config change**: RCON `stop` — Apex's panel daemon
  auto-restarts the Java process, no explicit "start" command needed. Server
  is unreachable via RCON for roughly 1-3 minutes during the restart.
- **`data get block` doesn't work for plain blocks** (pressure plates,
  etc.) — it only returns data for block *entities* (command blocks, chests,
  signs). To check a plain block's type reliably over RCON, use the
  `execute store success score ... if block X Y Z <block-id>` +
  `scoreboard players get` pattern instead (`execute if block` alone is
  known-flaky for feedback over RCON).

## Bringing the other 4 back

Jim, Beth, Benjamin, and Craig's full character prompts, coordinates
(`jim -140,66,170` / `beth -47,69,158` / `benjamin -63,65,205` /
`craig -68,65,218`), and villager professions (mason/mason/toolsmith/mason)
are recoverable from git history on:

- `evoke-infra/minecraft/config/billbot/npcs.json`
- `evoke-infra/minecraft/datapacks/keel_npcs/data/keel_npcs/function/load.mcfunction`

both as of the commit just before they were trimmed out (2026-07-17). To
restore: re-add their JSON entries with `"model":"gpt-4.1-nano"`, re-add
their `summon villager ...` lines with `Invulnerable:1b` included, FTP both
files up, restart.

## Open gaps (also tracked in `GAPS.md`)

- **API key is hardcoded** in `BillBot.java` (`API_KEY = "sk-..."`) as a
  stopgap — Apex's Java process doesn't have `OPENAI_API_KEY` set as an env
  var, and there's no per-app secrets mechanism on this host yet. Proper fix
  (env var support on Apex, or a server-side proxy) is not scheduled.
- **Datapack/config file on Apex only updates via manual FTP** — there's no
  automatic sync from the repo to the live server the way local Docker's
  `entrypoint.sh` does it. Any future edit to `npcs.json` or `keel_npcs`
  needs a manual FTP push + restart, both described above.
- **Nameplate JSON rendering bug** — see section above, not yet root-caused.
