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
- **Mod commands cannot appear in datapack functions** — the function
  parser rejects them at load time and the whole function silently fails
  (`Failed to load function` in the server log; every command in it goes
  dead, not just the offending line). Pattern: the datapack sets a
  scoreboard "mailbox" flag; the bridge's economy loop executes the mod
  command over RCON (`stipendDue`/`balanceWipe`). **After any datapack
  deploy, grep the server log for `Failed to load function`** — a
  `/reload` reports success even when functions failed to parse.
- OP testing skews: `/shop admin` toggle changes sign-click behavior;
  creative mode is exempt from the factory eviction; creative items can
  fake economy inputs.

---

## 10. Original-build content: port status

From the `basin` vs `true_oasis` command-block diff (2026-07-21, 141
unique commands). **Items 1–7 were ported later the same day** — datapacks
`basin_qol` and `basin_secrets` (new) plus `crafting_factory` extensions,
all live on Apex. Both new packs use the **self-scheduling tick pattern**
(`schedule ... 2t replace` armed by a `#minecraft:load` starter) so they
could go live via `/reload` + one manual `load` call, no restart.

1. **Factory XP-time economy** — PORTED (`crafting_factory:xp_time`, 5s
   cadence): Halyard box grants +1 level (cap 60), factory floor drains 1,
   warns at ≤5/≤1, ejects at 0 to `(6,94,98)`. The entry pad CB at
   `(2,92,98)` was live-patched back to the original gated command
   (`tp @p[level=60..] 319 123 -152`). XP levels = time you can afford.
2. **Conveyor emerald drops** — PORTED: ~1 emerald per 3 conveyor cycles
   (`random value 1..3` roll in `conveyor_drop`), the currency for the
   factory villagers.
3. **Craig's secret** — PORTED (`basin_secrets`): the town-hall basement
   tunnel was carved via structure export (it never existed in this
   lineage — solid andesite) and the terminal at `(-10,59,194)` runs
   `resetmoney` (tag-gated per visit). His NPC persona hints at it.
4. **Ethan's cookie stand** — covered by the staged `npc_lines` system
   (Ethan is a pen NPC); the original dialogue CB not separately ported.
5. **Diamond lightning ritual** — PORTED (`basin_secrets:tick`, global
   check exactly like the original) plus the mountain shrine structure at
   `(35-43,142-151,497-505)` with a new bone-block pedestal at
   `(39,146,501)` — the original world had **no bone block anywhere**, so
   the easter egg now has a discoverable home.
6. **Oasis content** — PORTED (`basin_qol`): one-time $100 arrival grant
   (tag `oasis_granted`, box `(86-105,136,1023-1049)`), and the
   Halyard→Oasis lift at `(35-38,88-91,57-60)`: consumes a `name_tag`
   credential → `tp 57 149 1095`; without one, a throttled "You need a
   ticket!". NOT ported: the "Plots for Oasis" tphub sign (admin
   convenience; needs a physical sign+button).
7. **Mines QoL** — PORTED (`basin_qol`): per-tier pickaxe repair station
   at the entrance, void rescue (deepened to y −30..5) with regeneration,
   FallDistance zeroing across the mine complex, one-time Halyard
   `spawnpoint` on train arrival (tag `halyard_spawned`).
8. **NPC reset buttons** in the tphub — obsolete; `keel_npcs` re-anchors.
9. **Alpha HQ / CEO-reveal ending** — still unbuilt (design exists in
   GAME_DESIGN canon; new construction, not recovery).

Also intentionally absent: ThirdBrain/any in-game LLM chat (school-safety
replacement is the staged-lines system + guarded web B1llBot), and
player-to-player chat.

---

## 12. How to play — the full arc (as deployed)

The intended player journey, end to end, with every command a player
actually types. Everything here is live.

**Setup.** Java: launcher pinned to 1.21.11 → Multiplayer →
`prosperity.apexmc.co`. Bedrock: latest release via the Geyser port. The
server is whitelist-only; linking (next step) auto-whitelists. Sync the
Field Tablet: scan the Ops Hub QR on a phone → accept the conduct charter
→ Simulator tab → "Link Your Minecraft Account" → type the shown code
in-game as `/trigger evoke_link set <code>` → confirm on the phone. From
here the tablet's **Basin Archive** narrates progress (6 memories unlock
automatically as the bridge detects each stage below).

**Act 1 — Keel (labor).** You wake on the ridge above town: look around
(all three tiers are visible), then walk down. Find Billbot's kiosk by
the villager pen — he whispers to you once. Grab the free iron pickaxe at
the worker station beside it ("Daily Task: Mine some coal"). Optional:
buy better tools at Benjamin's store, talk to Jim/Beth/Craig/the pen
villagers (staged lines; the greeting hands you a "relay chip" — the
in-world reason the tablet reaches Billbot). Enter the mines (sign at
`(-141,66,167)`; the lift refuses you without a pickaxe), get assigned a
random room, mine coal. Sell it at the `[Admin Shop] Coal` sign in the
room ($1/coal) or anywhere via `/trigger sellCoal`. Pickaxe worn out?
Hold it at the entrance repair station. Save **$100** → buy the paper
ticket at the station booth sign (or `/trigger buyTicket`) → step to the
train at `(-137,65,108)` — it consumes the paper and delivers you to
Halyard. Side content: coinflip (2 gold ingots), the donation bin
(Kindness badge), the hidden room/parkour near the kiosk, and — if Craig
ever tells you — a tunnel under the town hall (careful: its terminal
wipes your balance).

**Act 2 — Halyard (strategy + time).** Arrival sets your respawn to the
plaza. Two income engines: (1) **the Crafting Factory** — time itself is
the cost: being in Halyard builds XP levels (+1/5s, cap 60); the entry
pad at `(2,92,98)` requires 60; inside, levels drain, and at zero you're
ejected. Collect conveyor materials (red sand, obsidian, oak, cobble,
occasional **emeralds**), trade emeralds to the three villagers for the
exotic ingredients, craft the non-vanilla recipes, sell at the factory
shops (bookshelf $5 … beacon $200). (2) **combat** — the solo Mob Arena
or the co-op Mob Gauntlet; sell spider eyes/magma cream/slimeballs at
`(98,93,128-132)`. Meanwhile the rent machine teaches deadlines (unpaid
rent compounds 1.1×/sec). Goal: the **Name Tag credential** — 500
scoreboard-money at the ticket machine `(32,94,53)` or $1000 at the shop
sign — then stand on the lift at `(36,89,58)`: it consumes the tag and
raises you to the Oasis.

**Act 3 — Oasis (arrival).** You land at `(57,149,1095)`; a one-time
$100 settlement stipend credits on arrival. Content beyond the overlook
is the remaining build-out (plots, Alpha HQ ending).

**Building.** The delivered design (yawp region data in the true_oasis
save): exactly one protected zone — the town cuboid
`(-214,0,27)→(32,255,306)` (Keel + the Halyard plaza) — and free
building everywhere else in the huge world. Replicated on 1.21.11 with
gamemode enforcement in `basin_qol`: server default is **survival**;
inside the town cuboid players are flipped to adventure. Admins in
creative/spectator are never touched. (Not replicated: the region's
container-access denial — chests in town remain openable.)

**Easter egg:** drop a diamond onto a bone block (the shrine pedestal at
`(39,146,501)` is the intended spot) and wait ~1 second.

---

## 13. Gazetteer — key locations

| Location | Coordinates | Notes |
|---|---|---|
| Billbot's kiosk | `(-49,63,206)` | one-time whisper; golem at `(-49,65,208)` |
| Villager pen (chuzz/Ethan/Fredster) | `(-31.5,65,183.5)` area | staged lines |
| Worker station (free pickaxe) | `(-138,63,209-212)` | day-one badge |
| Benjamin's tool store | `(-63..-60,66,200)`, signs z=201 | $5/$10/$15 pickaxes, helmet $2 |
| Keel food buyers | `(-92..-90,65,131-137)` | sells food *to* Alpha |
| Coinflip stand | `(-141,66,141)` | 2 gold to play |
| Donation bin (Kindness) | `(-149,65,166)` | |
| Mines entrance / lift | `(-141,66,167)` sign; 2nd entrance `(503,66,269)` | pickaxe-gated |
| Mines rooms | y≈28-45, `(-137..-98, z -122..-70)` | coal shops at y=36 |
| Mines exit lobby | `(-105,61,151-153)` | `claimReward` trigger, badges |
| Pickaxe repair station | `(-138..-134,60-63,164-168)` | hold pickaxe |
| Keel train station | train `(-137,65,108-110)`; ticket booths `(-137,67,113)` & `(-137,67,102)` | paper $100 |
| Hidden room | `(75-82,62-67,145-154)` | teleport-swap trick |
| Parkour shaft | `(-16..2, y93→119, z93-121)` | prismarine ring at top |
| Halyard plaza / arrival | `(5,93,96)`, respawn `(6,93,91)` | |
| Rent / day-job machine | `(0-35,89-94,69-101)` | `stage` 0→6 |
| Factory entry pad | `(2,92,98)` | needs XP level 60 |
| Crafting factory | `(295-333,118-134,-154..-111)` | conveyor `(306,127,-134)` |
| Factory sell shops | `(320-329,123,-121..-114)` | |
| Claude's Halyard Mob Arena | `(-30..-24,70-76,90-102)` | solo, 5 waves |
| Mob Gauntlet | `(382,140,769)`+ room | co-op, 7 waves |
| Arena-drop buyers | `(98,93,128/130/132)` | spider eye $4 … |
| Name Tag ticket machine / shop | `(32,94,53)` / `(32,93,56-57)` | 500 money / $1000 |
| Oasis lift | `(35-38,88-91,57-60)` | consumes name_tag → Oasis |
| Oasis arrival | `(57,149,1095)` | stipend box `(86-105,136,1023-1049)` |
| Oasis overlook | `(58,135,1000)` | tphub destination |
| "Plots for Oasis" land | `(756,131,-367)` | undeveloped; no live tp |
| Craig's tunnel + terminal | tunnel `(-14..-5,56-63,188-199)`; terminal `(-10,59,194)` | resetmoney |
| Ritual shrine | `(35-43,142-151,497-505)`; pedestal `(39,146,501)` | diamond + bone block |
| Admin teleport hub | `(575-576,74,113-121)` | see §14 |
| Mirror town (east) | Keel duplicated at ~+648x | second mines entrance/train live there |

---

## 14. Admin tools: the teleporter and the trigger registry

**Becoming an admin in-world:** `op <username>` from the console (RCON or
Apex panel), then in-game `/tag @s add admin`. The `admin` tag — not OP
itself — is what the world's admin mechanics check.

**The teleport hub (tphub).** Type `/trigger tphub` from anywhere
(admin-tagged players only — command blocks across the map run
`execute as @a[tag=admin,scores={tphub=1..}] run tp @s 583 72 115`). You
arrive at the hub at `(583,72,115)`; five signed buttons teleport onward:

| Sign | Destination | What's there |
|---|---|---|
| "mines game (keel)" | `(-122,28,-79)` | inside the mines rooms |
| "halyard game" | `(331,123,-169)` | minecart ride / factory roof area |
| "halyard (dry)" | `(37,93,130)` | Halyard town |
| "halyard (post game)" | `(662,106,216)` | mirror-town Halyard |
| "oasis" | `(58,135,1000)` | the overlook |

(The original build had a sixth "Plots for Oasis" sign → `(756,131,-367)`
— not present in the live hub.)

**Player-typeable triggers** (vanilla `/trigger`, works on Bedrock too):

| Command | Who | Effect | Handled by |
|---|---|---|---|
| `/trigger evoke_link set <code>` | anyone | account linking | bridge `link_code_loop` |
| `/trigger sellCoal` | anyone | sells all coal/coal blocks for `$` | bridge `ticket_office_loop` |
| `/trigger buyTicket` | anyone | $100 → paper train ticket | bridge `ticket_office_loop` |
| `/trigger claimReward` | anyone at mines exit | +100 scoreboard-`money` (legacy, unadvertised, infinitely repeatable) | world CBs |
| `/trigger tphub` | `tag=admin` only | teleport to the admin hub | world CBs |

**Economy admin (savs, console-safe):** `bal <p>`, `baltop`,
`givemoney/takemoney/setmoney <p> <amt>`, `resetmoney <p>` (→ $10),
`/ecolog <target> <time> <unit>` (ledger). In-game only: `/shop create
sell|buy <price>`, `/shop remove`, `/shop admin` (**toggle — while on,
your sign clicks create admin shops instead of transacting; a common
source of "the shop is broken" during OP testing**).

**Full player reset to new-user state** (the tested recipe):
1. Postgres: delete their `minecraft_links` row, `mc_link_codes` rows,
   `basin_archive` `mc_quest_completions`, `mc_arena_best` /
   `mc_gauntlet_best` rows. Check `AUTO_LINK_PLAYER_ONE=false` on the
   bridge first, or the link comes back within a minute.
2. RCON (works offline): `scoreboard players reset <p>`, `resetmoney <p>`.
3. RCON (needs them online): `tag <p> remove admin` / `billbot_intro`,
   `gamemode survival`, `clear`, `xp set 0 levels` + `0 points`,
   `advancement revoke <p> everything`, `kill` (respawns at world spawn).
4. Leave them whitelisted — the fresh link flow requires joining.

**Other admin notes:** keep the scoreboard sidebar clear
(`scoreboard objectives setdisplay sidebar` with no argument clears it);
one-shot placement functions (`restored_shops:place_all`,
`basin_secrets:place`) are safe to re-run; `#minecraft:tick`/`load` tags
arm only on a real boot — after editing `basin_qol`/`basin_secrets` on a
running server, `/reload` then manually run the pack's `load` function to
re-arm its self-scheduling loop.

---

## 15. Related docs

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
