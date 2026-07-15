# MINECRAFT_WORLD_MAP.md — what's actually built in the Basin Simulation

This documents what's *actually in the world files*, not what's planned —
the gap between the two turned out to be substantial. Everything here was
found by exhaustively parsing the real region files (a stdlib-only NBT/Anvil
reader written for this, no external tools installed) and cross-checked
against `docs/legacy/`, `GAME_DESIGN.md`, and the live running server via
RCON. Coordinates and mechanisms below are verified, not inferred — either
read directly from block/command-block NBT, or confirmed live against the
running server.

None of this was known/written down anywhere before this investigation.
`GAPS.md` and `GAME_DESIGN.md` reference `basin` constantly but never
described what's actually built inside it.

---

## 1. World inventory

Three separate world saves exist at
`~/evoke-prosperity-files/minecraft/minecraft-world-files/` (outside the git
repo — see that directory's own README for why the 700MB+ saves aren't
committed).

| World | Size | Loader | Status |
|---|---|---|---|
| `basin` | 704MB | Fabric (custom mods: PolyFactory, Chisels & Bits, Biomes O'Plenty) | **The real, currently-deployed world** — confirmed mounted in the live `evoke-infra-minecraft-1` container (`/server/world-data/world`, matches the 704MB exactly). Everything in this doc except §7 lives here. |
| `unmodded/basin` | 720MB | Same as above | An earlier dev/test snapshot of the *same* build — identical mechanics plus extra scaffolding: more named test players (`Benjamin`, `Beth`, `Craig`, `Jim`, `AsherFur`, `MZC3`, `RKram`, `SenpaiHenrey`), debug `tp`/`clear`/`resetmoney` commands, two dead references to `givemoney`/`hasgold` (see §4). Not deployed. |
| `wil-world` | 6.5MB | Paper/Bukkit, MC 1.21.11 | **Confirmed empty of built content** via exhaustive scan: 2 sheep, a chest minecart, 2 vanilla cave-spider mineshaft spawners, and vanilla mineshaft/ancient-city structure pieces. No command blocks, no signs, nothing built. An abandoned prototype, not a real minigame world. Not deployed, not referenced anywhere else in this repo. |

**A second, separate set of world/mod exports** exists at
`~/evoke-prosperity-files/minecraft/servers/{playtest,water_is_life,wil_unmodded}/`
(each a `mods.zip` + `basin.zip`, found 2026-07-15) — not the same
files as the table above. None of the three bundled `mods.zip` matter for
the live deployment; the running server's `Dockerfile` builds its own
correct Geyser+Floodgate set fresh from Modrinth, independent of these.
Of the three `basin.zip` world saves: **`water_is_life`'s is the one
actually running today** (confirmed via matching region-file count and
`level.dat` against `evoke-infra/minecraft/world-seed/` and the live
container). `playtest` and `wil_unmodded` are divergent snapshots from a
different point in this world's history — `wil_unmodded` in particular
contains real, finished content that never made it into the live lineage:
see §11.

---

## 2. The real B1llbot kiosk

**Location:** `(-49, 63, 206)` in `basin`, region `r.-1.0.mca`, right next
to the starter villager pen (three unemployed desert villagers named
**chuzz**, **Ethan**, **Fredster** — the "NPC villagers at the start").

**Mechanism:** two command blocks, not a physical structure or GUI:
- `(-49, 62, 206)` — tags the player `billbot_intro` once
- `(-49, 63, 206)` — fires the message, gated on `tag=!billbot_intro`

(The static host copy at `~/evoke-prosperity-files/...` reads `(-49,62,206)`
as a `chain_command_block`; the live deployed server reads it as a plain
`command_block` — the one real discrepancy found between the two copies
during this investigation. See `scripts/minecraft-world-tools/README.md`.)

**Original message** (verbatim, still intact):
> *psst* hey! hey no one else in this city can see this kiosk so dont tell
> anyone. Anyway im billbot, you don't know me but I know you. Holler at me
> if you need help, I'll be watching you.

**This session extended it** (see `evoke-minecraft-bridge/bridge.py` git
history) to also carry the two-channel Minecraft-link code instructions,
appended to the same one-time message via a direct `data merge block`
rewrite of its `Command` NBT, verified against the live server.

**B1llbot also appears as a scripted "speaker" elsewhere** — the Halyard
geothermal-factory dialogue scene, built **twice** (region `r.0.0.mca` at
`(4,91,71)` and `r.1.0.mca` at `(648,91,173)`, near-identical text),
addressing the player by their canonical name **"Alex"**:
> \<Bi11Bot> Alex, This factory is more sustainable because it runs on
> Geothermal energy.
> \<Bi11Bot> So this is how they keep people trapped!

A dropped **"Starter Guide"** written book (author `Leanerdbeta6`) sits in
the same chunk as the villager pen.

---

## 3. The three real in-world minigames

All three are **live on the running server right now**. None are wired to
the web app (flagged, not built — see `GAPS.md`). Originally all three were
raw command blocks physically placed in the world save with no source file
anywhere; as of the 2026-07-14/15 robustness passes, all three are now
extracted into portable, version-controlled datapacks (same pattern
`mines_lift_precheck` already used for the mines entry check) — the
physical command blocks that used to hold the logic are now inert stubs or
a single trigger call, and the datapack file is the real source of truth.

### Coinflip gambling
`r.-1.0.mca`, ~`(-137 to -140, 62, 149)`. **Extracted**:
`evoke-infra/minecraft/datapacks/coinflip/`, function `coinflip:play`. A "2
gold to play" sign gates a coin flip — win pays 3 gold ingots, lose pays
nothing. Scoreboards: `coinflip`, `hasgold`. (The original raw version had a
real bug — the payout fired regardless of whether the player had actually
paid, a free-gold exploit; fixed as part of the extraction, see `GAPS.md`.)

### The mines (4-room randomized dungeon)
Entrance ~`(-140, 66, 168)`, "Enter the mines" sign; a second, previously
undocumented entrance/re-entry trigger also exists at `(503, 65, 266)`
(`r.0.0.mca`). Gated by a real pickaxe check (`mines_lift_precheck`
datapack, entry check only). The room-assignment + occupancy-detection
state machine (`room00`/`room01`/`room10`/`room11`, region `r.-1.-1.mca`
~chunks 787-825) is **extracted**: `evoke-infra/minecraft/datapacks/mines_room_randomizer/`,
functions `mines:assign_room` (called from both entrances) and `mines:tick`
(occupancy detection, on `#minecraft:tick`). Four pre-built room layouts
swapped in via structure blocks. Infinite admin coal shop and
auto-refilling unbreakable pickaxe (one instance per room) are separate,
simple, working mechanisms left as raw command blocks — out of scope for
this extraction, no bugs found in them.

The original raw version had two real bugs, both fixed as part of the
2026-07-15 extraction (the tick-order half was already patched live on
2026-07-14, see `GAPS.md`): the two physical entrances ran fully duplicate
13-block "watch for a global tag" processing chains instead of calling
shared logic directly, so a single tagged player was liable to be
double-processed by both; and 4 `gamemode adventure @s` commands meant to
lock rooms against griefing were mostly non-functional (3 of 4 were bare
commands with no `execute as` wrapper, so `@s` had no entity and they
always silently failed) while the one that did work (room00) had no
corresponding restore-to-survival anywhere in the entire world — it would
have permanently stranded a player unable to break blocks, including the
coal they're there to mine. Dropped entirely rather than "completed" for
the other 3 rooms.

### Minecart/dropper ride
`r.0.-1.mca`, ~`(304-306, 128-134, -142 to -144)`. **Extracted**:
`evoke-infra/minecraft/datapacks/minecart_ride/`, `#minecraft:tick` function
calling one `laneN.mcfunction` per rail. A timer loop per lane summons a
chest minecart every 80 ticks, fed by two droppers. (The original raw
version had all 3 lanes sharing one `rail1` counter instead of one each,
tripling the effective tick rate; fixed as part of the extraction.)

---

## 4. The Halyard day-job / rent economy

A `stage` 0→6 state machine (`r.0.0.mca` and its `r.1.0.mca` duplicate,
~`(0-35, 89-94, 69-101)`): clock in (10s wait) → work → clock out or incur a
compounding late fee → pay rent → pay misc. fees → optional debt relief →
buy a 500-money train ticket to progress toward Oasis.

**`money` is a plain vanilla scoreboard** (`scoreboard players add/remove/set
@s money N`) — confirmed by direct inspection of dozens of real command
blocks. It needs no mod. The `givemoney`/`resetmoney`/`hasgold`-*looking*
commands seen once in the `unmodded` dev snapshot are **dead, non-functional
references** to an abandoned economy mod
(`billbot_and_lore/Savs-Common-Economy`, an unfetched, empty git submodule —
confirmed empty on disk) that was apparently tried and then abandoned in
favor of plain scoreboard arithmetic, which is what actually shipped.

The rent-timer/late-fee half of this is already extracted as a portable
datapack (`evoke-infra/minecraft/datapacks/halyard_rent_functions/`, already
in the repo). The full clock-in/clock-out/fees state machine is **not** —
it only exists as raw command blocks in the world save.

---

## 5. Badges (written-book rewards)

Found via `give ... written_book_content` command blocks:

| Badge | Trigger |
|---|---|
| Keel's Finest Worker | First day, automatic |
| Perseverance | Mine coal despite hard conditions |
| Saver | "Save $100 irl" |
| Budgeteer | "Create a budget" |
| Monetary Master | Reach $200 |
| Kindness | Donate an item to the donation bin |
| Story | Read "The Old Oak" lore sign |
| Critical Thinker / Foresight | Signs only, in an "admin / control room" at y=180-181 (both `basin` and `unmodded`) — likely admin/testing signage, not confirmed as a live-earnable path |

---

## 6. The admin teleport hub

~`(575-576, 74, 113-121)`, near the Halyard factory. Admin-gated
(`tag=admin`, `tphub` scoreboard). Five destinations, each a sign + matching
`/tp` command block:

| Sign label | Destination | What's there |
|---|---|---|
| "halyard (post game)" | `(662,106,216)` | Not investigated further |
| "oasis" | `(58,135,1000)` | ~900 blocks from everything else, high altitude, zero command-block content nearby — likely a viewing/summit area, not a minigame |
| "mines game (keel)" | `(-122,28,-79)` | The mines entrance area (§3) |
| "halyard (dry)" | `(37,93,130)` | Not investigated further |
| "halyard game" | `(331,123,-169)` | The minecart ride area (§3) |

Admin re-entry point: `(583,72,115)`.

---

## 7. The hidden room + parkour shaft ("the hidden parkour")

Found this session by request — a real, deliberately hidden path from spawn
up to a small platform, verified block-by-block against the actual chunk
data (not just command-block text).

### Stage 1 — the hidden room
`(75-82, 62-67, 145-154)`, `r.0.0.mca`, near the villager pen/kiosk.
- Two proximity-trigger zones (**roomA** ~`(75,64,147)`, **roomB**
  ~`(78,64,146)`) that teleport-swap you into the *other* room's actual
  position — walk toward what looks like a dead end, get warped around an
  **invisible barrier wall** at `x=77` into the twin room instead.
- Two real iron doors at `(75,65,152)` and `(79,65,152)`.
- A real redstone mechanism: 4 pale-oak buttons, a sticky piston, redstone
  wire, a repeater, a lime-wool marker.
- Sealed under an invisible barrier-block roof at `y=68` — from outside/above
  it just looks like solid ground, which is why "no one else can see this
  kiosk" holds up architecturally, not just narratively.
- Two "EXIT" signs (pale oak wall signs), glowstone lighting, oak stairs
  down to reach it.

### Stage 2 — the climb
Leads up to a mid-level "trading station" / donation-bin area (~`y=93`, the
Kindness Badge mechanism, §5).

### Stage 3 — the parkour shaft
`x=-16 to 2, z=93-121, y=93 to ~119`. A hollow shaft between two walls 18
blocks apart:
- `y=93-103`: solid walls, deliberately unclimbable (the real base/entry).
- `y=105` upward: **scaffolding** climbing strips on both walls, in short
  segments separated by solid gaps — you climb, then have to jump the gap to
  the next segment. Floor/platform slabs cross the shaft at *different*
  z-positions per level (not stacked directly above each other), so it's a
  genuine climb-and-jump sequence, not a straight ladder.

### Stage 4 — the top
A ring-shaped **prismarine** platform (~12 blocks across, hollow ring, not
solid) floating alone at `y≈119-122`, open sky above. **No chest, sign, or
command block anywhere near it** — confirmed by both text search and a
direct material scan. The payoff is thematic, not material: prismarine is
the same glowing sea/water block used throughout Halyard's "Water Is Life"
storyline. You climb ~55 blocks from the hidden room to get there.

---

## 8. The B1llbot Fabric mod (in-game chat — currently blocked)

Two source trees at
`~/evoke-prosperity-files/minecraft/billbot_simple_chat_plugins/`:

| | `billbot` (built, v1.0.1) | `billbot_attempt_1` (v1.0.0, unbuilt) |
|---|---|---|
| Minecraft version | 1.21.10 | 1.21.10 |
| Fabric Loader | 0.16.10 | 0.16.14 |
| Status | **The one committed to this repo** (`evoke-infra/minecraft/mods/billbot-1.0.1.jar`) | Earlier draft, functionally a subset (no conversation history) |

**Both target the identical Minecraft version** — neither is more current,
no advantage to switching between them. The live server runs Minecraft
26.2; Fabric had published zero Yarn mappings for 26.2 as of this
investigation, so neither mod can be rebuilt/loaded until that changes
(matches `GAPS.md`'s existing note and `evoke-infra/minecraft/Dockerfile`'s
comment).

**What they do, once working:** intercept `@billbot`-prefixed chat, forward
to an OpenWebUI RAG endpoint (`https://prosperity.ngrok.dev/api/chat/completions`,
model `b1llbot`), reply prefixed `[BillBot]`. `billbot` keeps a rolling
20-message conversation history; `billbot_attempt_1` doesn't.

**Security note, unrelated to the version block:** both source files
hard-code a live-looking OpenWebUI API key as a fallback default
(`BillBot.java` and `OpenAIClient.java` respectively) — worth rotating or
removing if that key is real, independent of everything else in this doc.

---

## 9. Datapacks: extracted vs. world-only

Already portable and committed at `evoke-infra/minecraft/datapacks/`:
`custom_drops`, `halyard_rent_functions` (rent/late-fee half only),
`inventory_save`, `mines_lift_precheck` (entry check only),
`halyard_mob_arena` (see §10), `coinflip` and `minecart_ride` (2026-07-14),
and `mines_room_randomizer` (2026-07-15, entry-assignment + occupancy
detection — the coal shop and pickaxe auto-refill remain raw, see §3).
Each of these five newest extractions found and fixed at least one real
bug along the way, which is the whole reason they got pulled out — there
was otherwise nowhere for the fix to live durably.

**Still only raw command blocks in the world save**, not portable, not in
git: the full day-job stage machine, the hidden room + parkour shaft, the
teleport hub, every badge-granting command block, the mines' coal shop /
pickaxe auto-refill and exit-lobby triggers, and the B1llbot kiosk /
factory dialogue. If any of these ever need to survive a world rebuild or
be code-reviewed, they'd need the same extraction treatment the six
datapacks above already got.

---

## 10. What was built this session (cross-reference)

- Extended the real kiosk (§2) with link-code instructions —
  `evoke-minecraft-bridge/bridge.py`.
- **Halyard Mob Arena** — a real feature from `docs/legacy/All NPC and World
  Prompts/halyard-minigames.txt` that was designed but never built in any of
  the three worlds (confirmed by this same exhaustive scan). New datapack at
  `evoke-infra/minecraft/datapacks/halyard_mob_arena/`, physical room at
  `(-30 to -24, 70-76, 90-102)`, 5 waves, spider-eye economy, wired into the
  web app (XP, activity feed, Dossier stat tile).

---

## 11. Investigation tooling

Built this session, stdlib-only Python (no NBT libraries were installed or
needed) — now committed at `scripts/minecraft-world-tools/` (see that
directory's own README for usage and the workflow that actually found
everything in this doc):

- `mca_nbt_dump.py` — the foundational NBT/Anvil region-file parser
- `block_at.py` — decodes the actual block palette + bit-packed section data
  to answer "what block is at world X,Y,Z" (verified against known ground
  truth before trusting it — see the one static/live discrepancy it
  surfaced, noted in §2)
- `full_command_block_scan.py` — exhaustive command-block + spawner
  inventory across an entire world
- `scan_signs.py` — exhaustive sign-text inventory
- `scan_chunk_palettes.py` — fast per-chunk block-*material* search across a
  wide area, for areas with no command-block/sign text to grep (this is
  what actually found the parkour shaft in §7, once the other two scanners
  came up empty around the suspected spot)
- `render_slice.py` — ASCII top-down/vertical rendering + a "floating
  platform" detector, for turning a `scan_chunk_palettes.py` hit into an
  actual understanding of the shape
- `export_structure.py` — the write side: exports a bounding box of a world
  save as a vanilla structure `.nbt` (command blocks written out as air by
  design — logic belongs in a datapack's `.mcfunction` files, not baked into
  a relocatable structure). Built to pull the Mob Gauntlet's room out of
  `wil_unmodded` (§11 below); works on any world save, not just that one

Worth reusing for checking `unmodded` more thoroughly, mapping the rest of
Halyard/Oasis, or verifying any future direct world edit before it ships.

---

## 12. The Mob Gauntlet (ported from `wil_unmodded`, 2026-07-15)

A real, finished 7-wave co-op combat arena existed in the `wil_unmodded`
`basin.zip` snapshot (§1) but never made it into the world lineage
actually running today. Found via `full_command_block_scan.py` +
`scan_signs.py` against that snapshot: wave-number signs (1 through 8, wave
6 marked "Reward") at `~(391-405, 141, 823)`, and — tellingly — a sign
reading **"halyard arena"** at the admin teleport hub (`580,74,117`) with a
teleport to `420,141,833`, right at this room's entrance. This session
independently built and shipped an unrelated arena under the name "Halyard
Mob Arena" (§10) with no knowledge this already existed under essentially
the same name in a different world lineage. **Resolved 2026-07-15**: the
session-built arena is now **Claude's Halyard Mob Arena** everywhere a
player or web user sees it — the in-world banner, its sign, the win
message, and the web feed/toast text all updated and redeployed live. The
underlying datapack folder and namespace (`halyard_mob_arena`/
`halyard_arena`) were deliberately left as-is — internal identifiers, not
player-facing, not worth the redeploy churn of a namespace change.

The room itself was a genuine, precisely-bounded builder-saved structure
(`generated/minecraft/structures/my_mob_room.nbt` in that snapshot, 23×19×40,
17,480 blocks) — extracted with `export_structure.py`, its one baked-in
command block stripped, and shipped as
`evoke-infra/minecraft/datapacks/mob_gauntlet/data/mob_gauntlet/structure/room.nbt`,
placed via `place template mob_gauntlet:room` at the exact same absolute
coordinates it occupied in the source snapshot (`382,140,769` — nothing
else occupies that space in the live world, so no coordinate translation
needed). All command/game logic was reimplemented cleanly as `.mcfunction`
files rather than carried over as stale, absolute-coordinate-dependent
`Command` NBT.

**Mechanically distinct from the Halyard Mob Arena:** co-op (titles and
safety checks target everyone within 100 blocks, not a single player, per
the original's own design), randomized spawn positions (30 invisible marker
entities scattered via `spreadplayers` each wave, mobs summon at random
marker positions rather than fixed points), and most mobs are `Size:3` —
actual giant-scaled versions, not just larger counts. Composition escalates
across 7 waves: husk → silverfish → slime+skeleton →
blaze+wither_skeleton+magma_cube → piglin_brute ×16 →
pillager+stray+ravager → ravager+baby zombies (final wave).

**Two real issues found and fixed during the port**, same category as
every other raw-command-block extraction this session:
- The original had exactly this idea — an unconditional mob cleanup gated
  on "no player within 50 blocks" — split across two physically separate
  command blocks (`execute unless entity @a[distance=..50]` with no `run`
  clause, followed by a bare, unconditional `kill`), so the condition never
  actually gated anything. Fixed as one real command in `run.mcfunction`,
  and re-centered on the actual room (the original's un-specified default
  center was the control corridor, ~40 blocks from the room itself).
- Two dead-code test waves ("Wave Cow" — a `Size:3` cow — and a stray
  "Thanks for playing..." title tied to a villager spawn) sat in the middle
  of the build order but were never reachable by the real state machine's
  branching logic (which only ever dispatches wave numbers 1-9 or a
  wave-10 reset, none of which route to those two blocks). Left out of the
  port as confirmed-dead test scaffolding, not real content.

**Bridge/XP wiring added 2026-07-15**, mirroring the Halyard Mob Arena's
`ArenaWaveReached`/`mc_arena_best` pattern exactly: a `gauntletBestWave`
scoreboard, ratcheted per-player but credited to *everyone* within 100
blocks when a wave clears (matching this arena's co-op design, unlike the
solo arena's single-player ratchet), `check_gauntlet_progress` in
`bridge.py` (own `mc_gauntlet_best` table, `GAUNTLET_XP_PER_WAVE=30` vs.
the solo arena's 20), `GET /api/mc-gauntlet/{user_id}`, a
`GauntletWaveReached` event (feed message + toast), and a "Gauntlet Best"
Dossier stat tile. Verified: the datapack logic runs with no syntax
errors, and the full Postgres → API read path round-tripped correctly with
a manually inserted row.

**Still not done:** the entry pressure plate's exact tile was placed by
approximation near the original's "Start game" sign rather than verified
against real foot traffic, and the live RCON-heartbeat path (a real
connected player actually clearing a wave, end to end) hasn't been
exercised — no player was online to drive it. Worth a live walk-through
before calling this launch-ready. Verified so far: the structure placed
identically to source (20/20 targeted block samples matched exactly
against the original NBT), and all functions run with no syntax errors.
