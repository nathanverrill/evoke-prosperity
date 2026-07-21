# MINECRAFT_GAME_REFERENCE.md — the canonical map of the Basin Simulation

**Audience: AI agents and developers working on this repo.** This is the
single entry point for "what exists in the Minecraft game, how it works,
and how to hook into it." It reflects the deployed state as of
**2026-07-21** (savs-economy restored, NPCs restored, Basin Archive live,
shop kiosks placed). [`MINECRAFT_WORLD_MAP.md`](MINECRAFT_WORLD_MAP.md)
remains valuable for the investigation history and deep coordinates of the
`basin` lineage, but several of its status claims are superseded here
(server version, billbot mod status, economy mod status).

---

## 1. Deployment truth

| Thing | Value |
|---|---|
| Live server | Apex Hosting, `prosperity.apexmc.co` = `98.142.5.162` |
| Minecraft version | **1.21.11**, Fabric loader 0.19.3 (26.2 was tried and reverted — no mappings; see Dockerfile header) |
| Game ports | Java on the default srv-resolved port; Bedrock via Geyser UDP 19132 |
| RCON | **Port 25575** (not 25714 — that port is open but is not RCON), password in root `.env` as `MINECRAFT_BRIDGE_RCON_PASSWORD` |
| FTP (deploys) | Root is `default/`; world dir is `default/basin/`; mods `default/mods/`; config `default/config/` |
| World running live | `basin` (the water_is_life lineage — see §2) |
| Whitelist | **Enforced.** Auto-add happens on EVOKE account link (`handle_minecraft_linked` in bridge.py) |
| Local mirror | `evoke-infra-minecraft-1` container, same image (`evoke-infra/minecraft/Dockerfile`), RCON localhost:25575 password `devsecret123` |
| Web app | `evoke-web-1` container (localhost:8000, public via evoke.ngrok.app) |
| Bridge | `evoke-minecraft-bridge-1` container — currently reaches Apex RCON **over the internet**; the safety brief's co-hosted architecture is the target, not today's topology |

**Deploy patterns:** datapack/config changes → FTP upload → `/reload` +
manually run the function (`#minecraft:load`/`#minecraft:tick` tags do
**not** re-arm on `/reload`, only on a real boot). Mod changes → FTP + a
panel restart. The repo Dockerfile mirrors the Apex mod/config set so a
rebuilt image matches the live server.

---

## 2. World files: which one to look at

All under `~/evoke-prosperity-files/minecraft/` (not in git — too big).

| World save | What it is | Use it for |
|---|---|---|
| `minecraft-world-files/basin/` (705MB) | **Static copy of the live world lineage** (water_is_life). One known one-block discrepancy vs live (see world map §2). | "What is actually on the live server" questions. |
| `servers/playtest/true_oasis/` (739MB, 240 regions, has datapacks) | **The authoritative original build.** `true_oasis` is the world the original internship server actually ran — proven by `will-other-server-files/server.properties` (`level-name=true_oasis`). The playtest copy is the most complete: it has the shop kiosks, the factory XP-time mechanic, the Oasis content, and matches `shops.json`. | "How did the original build do X" questions. This is "the appropriate true_oasis." |
| `servers/wil_unmodded/true_oasis/` (Jul 8) and `cu-internship/true_oasis/` (May 4) | Earlier snapshots of the same build. | Cross-checking history. |
| `servers/water_is_life/true_oasis/` (218 regions, no datapacks) | **A stripped/earlier state despite its later mtime** — shop kiosks are air here. Do not treat as authoritative. | Rarely. |
| `minecraft-world-files/unmodded/basin/` | Dev snapshot of the basin lineage: extra test players, debug commands, dead `givemoney` references. | History only. |
| `minecraft-world-files/wil-world/` | Confirmed empty Paper prototype. | Never. |
| `evoke-infra/minecraft/world-seed/` | The basin copy baked into the Docker image (its `datapacks/` is empty on purpose — repo datapacks sync at boot). | Image builds. |

**Key lineage fact:** the live `basin` world diverged from `true_oasis`
*before* the shop kiosks, factory XP-time system, and Oasis content were
built. Everything "missing vs original" traces to that split. The shop
kiosks were re-ported 2026-07-21 (`restored_shops` datapack); the rest is
listed in §10.

**Investigation tools:** `scripts/minecraft-world-tools/` (stdlib-only
NBT/Anvil readers — see its README). `full_command_block_scan.py` +
`scan_signs.py` on a world save answer most "what exists" questions.

---

## 3. Mods: which files are correct

**Live on Apex right now (verified via FTP `default/mods/`):**

| Jar | Role | Canonical source |
|---|---|---|
| `fabric-api-0.141.5+1.21.11.jar` | Fabric API | Modrinth (URL pinned in Dockerfile) |
| `Geyser-Fabric-2.9.6-b1133.jar` | Bedrock clients | Modrinth (Dockerfile) |
| `Floodgate-Fabric-2.2.6-b60.jar` | Bedrock auth without Java accounts | Modrinth (Dockerfile) |
| `billbot-2.0.0.jar` | **Staged NPC dialogue + total player-chat block.** No LLM calls. | Source: `~/evoke-prosperity-files/minecraft/billbot_simple_chat_plugins/billbot/` (`ProsperityDialog.java`); built jar committed at `evoke-infra/minecraft/mods/billbot-2.0.0.jar` |
| `savs-common-economy-1.5.1-1.21.11.jar` | The economy: `$` balances, sign shops, `/withdraw` bank notes | Modrinth project `savs-common-economy` (URL pinned in Dockerfile). Same 1.5.1 the original ran, rebuilt upstream for 1.21.11 |

**Original build's mod set** (reference only): `cu-internship/Snapshot of
Mods Used/Server/mods/` — adds `thirdbrain` (LLM NPC chat — **removed
deliberately for school use, never restore**), `styled-chat`, ViaVersion/
ViaFabric, worldedit, yawp. The `billbot-1.0.1.jar` era (direct OpenWebUI
calls, hard-coded API key) is dead; v2.0.0 replaced it.

**Mod configs (project content, in git):**
- `evoke-infra/minecraft/config/billbot/npcs.json` — NPC chat spots
  (name/x/y/z/range). Read at **mod startup only**; changing it needs a
  server restart.
- `evoke-infra/minecraft/config/savs-common-economy/{config.json,shops.json}`
  — economy config + all shop registrations (recovered from
  `will-other-server-files/config/savs-common-economy/`). `balances.json`
  is runtime state, lives only on the server (Apex copy currently holds
  $1000 admin speedrun balances for the test crew; default start is $10).

---

## 4. The two currencies (do not conflate)

| Currency | Backed by | Earned via | Spent via |
|---|---|---|---|
| **`$` (mod balance)** | savs-common-economy (`balances.json`) | Selling coal at the mines `[Admin Shop]` signs ($1/coal registration; older sign faces read $0.5), `/trigger sellCoal` (bridge, $1/coal, $9/coal block), selling arena drops / factory products at Halyard shops, Oasis arrival grant ($100 box — true_oasis only, not live) | Pickaxe store, $100 paper train ticket (booth sign or `/trigger buyTicket`), $1000 Name Tag (Oasis ticket), `/withdraw` bank notes |
| **`money` (vanilla scoreboard)** | plain scoreboard | Halyard day-job stage machine (clock-in wages), `/trigger claimReward` (+100, mines exit, honor-system, **not advertised** — infinite-claim exploit) | Halyard rent/fees, the 500-money leg of the Halyard→Oasis machine |

Mod commands usable from RCON/console: `bal <p>`, `givemoney <p> <amt>`,
`takemoney <p> <amt>`, `setmoney`, `resetmoney <p>` (→ $10), `baltop`,
`/ecolog` (transaction ledger). `/sell` commands are disabled in config —
selling is via sign shops (or the bridge triggers).

**Known loophole:** the train accepts *any* `minecraft:paper`, and
`/withdraw 1` mints paper — an effectively free ticket for anyone who
knows the command. The taught path is the $100 booth. Patch idea (not
done): make the train require a named item.

---

## 5. Mechanics catalog (live world)

Coordinates are live-verified unless noted. "CB" = raw command blocks in
the world save (no source file); "DP" = datapack in
`evoke-infra/minecraft/datapacks/` (git = source of truth).

### Keel (start of game; spawn is on the ridge above town)

| Mechanic | Where | How it works | State it touches |
|---|---|---|---|
| Billbot kiosk (one-time intro + link instructions) | `(-49,63,206)` | CB pair; fires once per player | tag `billbot_intro` |
| Billbot NPC (copper golem) + Jim/Beth/Benjamin/Craig villagers | `(-49,65,208)`, `(-140,66,170)`, `(-47,69,158)`, `(-63,65,205)`, `(-68,65,218)` | DP `keel_npcs` summons (storage-flag idempotent); **dialogue = billbot mod** proximity/`@name` chat serving staged lines from `GET /api/npc-lines` (DB table `npc_lines`, editable live, refreshes ~5min) | storage `keel_npcs:state` |
| Starter villager pen (chuzz/Ethan/Fredster) | `(-31.5,65,183.5)` area | Real name-tagged villagers (chuzz/Fredster organic; Ethan DP-summoned via `keel_villager_pen`); staged lines same system | storage `keel_villager_pen:state` |
| Day-one worker station | `(-138,63,209-212)` | CB: free iron pickaxe + "Keel's Finest Worker" badge book + "Daily Task: Mine some coal." | `seenMsg` |
| Benjamin's tool store | chests `(-63..-60,66,200)`, signs at z=201 | savs sign shops: wooden $5 / stone $10 / iron $15 pickaxe, iron helmet $2. Physical kiosk from DP `restored_shops` | shops.json |
| Food buyers | `(-92..-90,65,131-137)` | savs: buys apple $3, steak $8, golden carrot $10, cooked rabbit $5 | shops.json |
| The mines | entrance sign `(-141,66,167)`, 2nd entrance `(503,66,269)` | DP `mines_lift_precheck` (pickaxe required to ride lift) + DP `mines_room_randomizer` (4 rooms via `room00/01/10/11` occupancy fake-players; players tp'd to y≈40 rooms). CB: infinite coal chests, per-room unbreakable pickaxe refill, exit tp `(-139,65,155)` | `room`, tag `mine_tp` |
| Coal wage | in-room signs `(-103,36,-106)`, `(-130,36,-76)` etc. | savs `[Admin Shop] Coal — Buying` ($1/coal per registration). Anywhere-equivalent: `/trigger sellCoal` (bridge) | `$` balance |
| `gotCoal` detector | CB `(-104..-101,61,152-153)` | any player with coal in hotbar → `gotCoal 1`, Perseverance badge, → 2 | `gotCoal` |
| Wage claim (unadvertised) | mines exit lobby `(-105,61,151-153)` | CB trigger `claimReward` → +100 `money` | `claimReward`, `money` |
| Coinflip gambling | `(-141,66,141)` area | DP `coinflip` — 2 gold ingots to play, win pays 3 | `coinflip`, `hasgold`, `bet` |
| Train to Halyard | ticket check `(-139,64,108)`, consume+tp `(-137,65,108-110)` → `(5,93,96)` | CB: requires any `minecraft:paper`, consumes 1. Tickets: booth signs `(-137,67,113/102)` sell paper $100 (DP `restored_shops` + shops.json), or `/trigger buyTicket` (bridge, $100) | inventory |
| Hidden room + parkour shaft | `(75-82,62-67,145-154)` → shaft `(-16..2, 93-119, 93-121)` | pure architecture + tp-swap CBs; prize is thematic (prismarine ring), **no material reward exists** | — |
| Badges (written books) | various CBs | Keel's Finest, Perseverance, Saver, Budgeteer, Monetary Master ($200 money), Kindness (donation bin `(-149,65,166)`), Story | `kindness`, `moneyBadgeClaimed` |

### Halyard (mid tier; arrive at `(5,93,96)`)

| Mechanic | Where | How it works | State |
|---|---|---|---|
| Day-job / rent stage machine | `(0-35,89-94,69-101)` + mirror at +648x | CB `stage` 0→6: clock in (10s), work, clock out or compounding late fee, pay rent, fees, optional debt relief, 500-`money` ticket leg. Rent/late-fee half is DP `halyard_rent_functions` (`rentTimer`, `lateFee` 1.1×/sec — **this is the "compounding interest" teaching mechanic**) | `stage`, `money`, `rent`, `rentTimer`, `rentPaid`, `late*`, `fees` |
| Claude's Halyard Mob Arena (solo, 5 waves) | room `(-30..-24,70-76,90-102)` | DP `halyard_mob_arena`; spider-eye economy; web-wired | `arenaWave`, `arenaBestWave`, `arenaActive`, `arenaDeaths` |
| Mob Gauntlet (co-op, 7 waves, giant mobs) | room `(382,140,769)`+ | DP `mob_gauntlet` (structure + functions, ported from true_oasis lineage); credits everyone within 100 blocks | `gauntletBestWave`, `gauntlet.*` |
| Arena-drop buyers | signs `(98,93,128/130/132)` | savs: spider eye $4, magma cream $10, slimeball $20 (DP `restored_shops`) | `$` |
| Crafting factory | `(295-333,118-134,-154..-111)` | DP `crafting_factory`: material conveyor (drop point `(306.89,127,-134)`, 60-tick timer, 40-item cap) + 3 trading villagers (Overworld/Nether/Ender — emerald trades for rabbit hide, slime, blaze rod, nether star, ender pearl, chorus fruit). Sell shops: savs signs (DP `restored_shops`): bookshelf $5, activator rail $2, end rod $14, sticky piston $8, cake $20, beacon $200. Recipes are non-vanilla (see `cu-internship/All NPC and World Prompts/halyard-minigames.txt`) | `cf_conveyor` |
| Minecart/dropper ride | `(304-306,128-134,-142..-144)` | DP `minecart_ride` — chest minecart per lane per 80 ticks | `cartTimer`, `cartRand` |
| Halyard→Oasis ticket | sign "Purchase ticket Cost: 500" `(33,94,56)`; CB `(32,94,53-54)` | 500 `money` → name_tag; also savs shop: Name Tag $1000 `(32,93,56-57)` (DP `restored_shops`) | `money`, `$` |
| B1llbot factory dialogue | `(4,91,71)` + mirror | CB scripted scene addressing "Alex" | `halyardFactoryDialoguePlayed` |

### Oasis & meta

| Mechanic | Where | Notes |
|---|---|---|
| Oasis viewing area | `(58,135,1000)` | tphub destination; little built content in live world |
| Admin teleport hub | `(575-576,74,113-121)` | `tag=admin` + `/trigger tphub`; 5 signed destinations + NPC-reset buttons existed in true_oasis |
| Keel Restoration Beacon | anchored via `world_meta` or `KEEL_BEACON_POS` | bridge builds a growing monument per cohort world-stage (`WorldStateAdvanced`) |
| Basin Archive detection | boxes in bridge.py `POSITION_FLAGS` | see §7 |

---

## 6. Scoreboard & tag registry (the integration ABI)

Player-scoped objectives that mean something (full live list is ~60):

- `money` — vanilla-scoreboard currency (Halyard machine)
- `gotCoal` — 0 none / 1 has coal / 2 badge given (world-set, global)
- `basinSeen`, `keelVisited`, `minesVisited`, `halyardVisited` — set by the
  bridge for **linked** players (presence + position boxes); drive the
  Basin Archive quests
- `evoke_link` (trigger) — account-link code entry
- `sellCoal`, `buyTicket` (triggers) — bridge economy office
- `claimReward` (trigger) — CB wage claim
- `arenaBestWave`, `gauntletBestWave` — ratchets the bridge converts to XP
- `rentPaid`, `rentTimer`, `lateFee`, `stage` — Halyard economy
- `coinflip`, `hasgold`, `bet` — coinflip
- `kindness`, `moneyBadgeClaimed`, `seenMsg` — badges/one-time gates

Tags: `billbot_intro` (kiosk fired), `mine_tp` (mines routing), `admin`
(tphub access), `keel_npc_*` / `keel_pen_*` (NPC entities).

**Display slots:** keep the sidebar clear — a leftover
`setdisplay sidebar kindness` from the original build was cleared
2026-07-21; nothing should re-set it.

---

## 7. Integration surfaces (how the web app sees the game)

### The bridge (`evoke-minecraft-bridge/bridge.py`) — 8 async loops

| Loop | Interval | Does |
|---|---|---|
| `event_consumer_loop` | poll | Kafka → in-game reactions: `LevelUpped` (title/sound/particles), `MissionCompleted` (broadcast), `TeamWheelCompleted`, `WorldStateAdvanced` (beacon), `MinecraftLinked` (whitelist add), `RewardCollected` (tier → `mc_reward_catalog` item/effect delivery) |
| `offline_delivery_loop` | 60s | queued rewards (`mc_reward_grants`) when player comes online |
| `heartbeat_loop` | 60s | online XP tick (5/min), arena+gauntlet ratchet checks, lore lines (via LiteLLM guardrails), optional Player One auto-link (`AUTO_LINK_PLAYER_ONE`, **false in prod**) |
| `presence_loop` | 15s | `MinecraftPresence` snapshots (web "who's in the Basin" card) |
| `quest_trigger_loop` | 30s | **the generic hook**: `mc_quest_triggers` rows (quest_id, objective, threshold) × linked players → reads scoreboards via RCON → `mc_quest_completions` + `QuestCompleted` + `XPGranted` + tellraw |
| `link_code_loop` | 10s | two-channel account linking (`mc_link_codes` ↔ `/trigger evoke_link`) |
| `world_progress_loop` | 15s | sets `basinSeen` + position-box flags for linked players (`POSITION_FLAGS` const) |
| `ticket_office_loop` | 5s | `/trigger sellCoal` (clear coal → `givemoney`) and `/trigger buyTicket` (`bal`/`takemoney` → paper) |

### Web app (`evoke/main.py`)

- `GET /api/minecraft/connect-info` — addresses/version for clients
- `POST /api/minecraft/link-code`, `GET .../link-request/{u}`, `POST .../link-confirm` — the link flow
- `GET /api/basin-archive/{u}` — the tablet's memory chain (`BASIN_ARCHIVE` const = content; unlock = link state + `mc_quest_completions` on `kind='basin_archive'` quests)
- `GET /api/mc-quests`, `POST /api/mc-quests/{id}/submit` — quest list / honor-system submit
- `GET /api/mc-arena/{u}`, `GET /api/mc-gauntlet/{u}` — best-wave reads
- `GET /api/npc-lines` — staged NPC dialogue (the billbot mod polls this)
- `GET /api/minecraft/status` — presence projection (OpenSearch `minecraft-status`)
- `/ws` — live push; every worker-processed event type is broadcast as `{type, data}`

### Postgres tables

`minecraft_links`, `mc_link_codes`, `mc_quests`, `mc_quest_triggers`,
`mc_quest_completions`, `mc_quest_submissions`, `mc_reward_catalog`,
`mc_reward_grants`, `mc_arena_best`, `mc_gauntlet_best`, `world_meta`
(bridge-owned), `npc_lines`, `billbot_chat_log`.

---

## 8. Hook-in recipes

**Auto-completing quest from any in-world act** (the standard pattern):
1. Make the world set a per-player scoreboard (datapack or CB, or a bridge
   loop for things the world can't see — position, presence).
2. Insert an `mc_quests` row (`kind='basin_archive'` for tablet memories,
   `'mission_quest'`/`'side_quest'` otherwise) + an `mc_quest_triggers`
   row (objective, threshold). Seeding lives in main.py's startup block.
3. Done — `quest_trigger_loop` handles dedupe, XP, events, tellraw. For
   tablet display add an entry to `BASIN_ARCHIVE` in main.py.

**NPC dialogue change:** UPDATE `npc_lines` in Postgres — live within ~5
minutes, no deploy. New NPC = summon entity (extend `keel_npcs` DP) + add
chat spot to `config/billbot/npcs.json` (needs server restart) + seed
lines.

**New shop:** either register in `shops.json` + place chest/sign (an OP
in-game can use `/shop create`, or port blocks from `true_oasis` via
`export_structure.py` → `restored_shops` pattern), or add a bridge
trigger like `sellCoal` for a command-based equivalent.

**In-game reaction to a web event:** add a handler in bridge
`process_event` — the bridge consumes every `evoke-events` /
`minecraft-events` topic message.

**Direct world edits:** RCON `setblock`/`data merge block`. Verify with
`data get block` (RCON `execute if block` is flaky — see memory/gotchas).

---

## 9. Operational gotchas (hard-won)

- `/reload` registers new datapacks/functions but does **not** arm
  `#minecraft:tick`/`#minecraft:load` — run functions manually or restart.
- `CustomName` is a text component since 1.21.5: use `CustomName:"Name"`,
  never `'{"text":"Name"}'` (renders raw JSON).
- Entity/block queries need loaded chunks — `forceload add x z`, query,
  `forceload remove`. "No entity was found" often means "chunk not
  loaded", not "doesn't exist".
- Entity-existence idempotency checks race forceload at boot — use
  command-storage flags (see `keel_npcs/load.mcfunction` header).
- `clear <p> <item> 0` returns a count without removing (the world's own
  `hasgold` pattern); destructive `clear` responses parse as
  `Removed N ...` / `No items were found`.
- Player-targeted commands fail for offline players; scoreboards and mod
  balances (`bal`, `givemoney`) work offline.
- The billbot mod blocks **all** player chat; `/trigger` commands and
  `/tell`-style feedback via `tellraw` are the only channels.
- Always-active, uncapped item-append CBs flood (the coal-block incident);
  cap-and-count like `crafting_factory`'s conveyor.
- OP testing skews: `/shop admin` toggle changes sign-click behavior;
  creative mode is exempt from the factory eviction; creative items can
  fake economy inputs.

---

## 10. Original-build content NOT yet in the live world

From the `basin` vs `true_oasis` command-block diff (2026-07-21, 141
unique commands), beyond what's already ported:

1. **Factory XP-time economy** (the "time scarcity" teaching mechanic):
   inside Halyard a box grants +1 XP level (cap 60) — CBs at
   `(40-41,89,104)`; the factory drains 1 level/tick-interval
   (`(324,118,-150..-152)`), warns at ≤5 ("Time to go!") and ≤1
   ("I warned you!"), ejects at 0 to `(6,94,98)`, and blocks re-entry
   under level 60 (`(4,92,100)`). XP levels = time you can afford inside.
2. **Conveyor emerald drops** — the original conveyor also dropped
   emeralds via `#roll rng` (needed for the factory villager trades). Our
   `crafting_factory` port drops only red_sand/obsidian/oak_log/
   cobblestone. **Real gap: players currently have no emerald source.**
3. **Craig's secret** — town-hall basement `resetmoney @p` control panel
   at `(-10,59,194)` (his NPC prompt hints at it under duress).
4. **Ethan's cookie stand** — dialogue CB at `(-26,64,184)`.
5. **Diamond-on-bone-block lightning ritual** — easter egg at
   `(37-39,147-150,501)`: a dropped diamond on a bone block charges
   (`skelly` counter, crit particles) then a lightning strike.
6. **Oasis content**: $100 arrival grant box `(86-105,136,1023-1049)`
   (`givemoney` — mod currency), tp chain into Oasis locations
   (`57,149,1095`, `97,137,1036`), "Plots for Oasis" tphub destination
   `(575,74,123)→(756,131,-367)`.
7. **Mines QoL from true_oasis**: per-tier pickaxe auto-repair
   (`(-138..-135,60-62,164-167)`), void rescue tp, regeneration box,
   Halyard `spawnpoint` set on arrival.
8. **NPC reset buttons** in the tphub (tp each NPC to post) — partially
   obsolete now that `keel_npcs` re-anchors them.
9. **Alpha HQ / CEO-reveal ending** — designed (GAME_DESIGN canon), only a
   hanging sign exists anywhere. New construction, not recovery.

Also intentionally absent: ThirdBrain/any in-game LLM chat (school-safety
replacement is the staged-lines system + guarded web B1llBot), and
player-to-player chat.

---

## 11. Related docs

- [`MINECRAFT_WORLD_MAP.md`](MINECRAFT_WORLD_MAP.md) — deep coordinates +
  investigation history of the basin lineage (pre-2026-07-21 status lines
  superseded by this doc)
- [`GAME_DESIGN.md`](GAME_DESIGN.md) — narrative canon, characters, the
  mission↔minigame mapping intent
- [`MINECRAFT_MINIGAMES.md`](MINECRAFT_MINIGAMES.md) — student-facing
  minigame framing
- `cu-internship/All NPC and World Prompts/` — original NPC personas and
  zone teaching-focus docs (the financial-literacy intent per zone)
- [`WHITELIST.md`](WHITELIST.md), [`SAFETY.md`](SAFETY.md),
  [`GAPS.md`](GAPS.md) — access, safety posture, known gaps
