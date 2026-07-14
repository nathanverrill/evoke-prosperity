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
`GAPS.md` and `GAME_DESIGN.md` reference `true_oasis` constantly but never
described what's actually built inside it.

---

## 1. World inventory

Three separate world saves exist at
`~/evoke-prosperity-files/minecraft/minecraft-world-files/` (outside the git
repo — see that directory's own README for why the 700MB+ saves aren't
committed).

| World | Size | Loader | Status |
|---|---|---|---|
| `true_oasis` | 704MB | Fabric (custom mods: PolyFactory, Chisels & Bits, Biomes O'Plenty) | **The real, currently-deployed world** — confirmed mounted in the live `evoke-infra-minecraft-1` container (`/server/world-data/world`, matches the 704MB exactly). Everything in this doc except §7 lives here. |
| `unmodded/true_oasis` | 720MB | Same as above | An earlier dev/test snapshot of the *same* build — identical mechanics plus extra scaffolding: more named test players (`Benjamin`, `Beth`, `Craig`, `Jim`, `AsherFur`, `MZC3`, `RKram`, `SenpaiHenrey`), debug `tp`/`clear`/`resetmoney` commands, two dead references to `givemoney`/`hasgold` (see §4). Not deployed. |
| `wil-world` | 6.5MB | Paper/Bukkit, MC 1.21.11 | **Confirmed empty of built content** via exhaustive scan: 2 sheep, a chest minecart, 2 vanilla cave-spider mineshaft spawners, and vanilla mineshaft/ancient-city structure pieces. No command blocks, no signs, nothing built. An abandoned prototype, not a real minigame world. Not deployed, not referenced anywhere else in this repo. |

---

## 2. The real B1llbot kiosk

**Location:** `(-49, 63, 206)` in `true_oasis`, region `r.-1.0.mca`, right next
to the starter villager pen (three unemployed desert villagers named
**chuzz**, **Ethan**, **Fredster** — the "NPC villagers at the start").

**Mechanism:** two command blocks, not a physical structure or GUI:
- `(-49, 62, 206)` — chain command block, tags the player `billbot_intro`
  once
- `(-49, 63, 206)` — fires the message, gated on `tag=!billbot_intro`

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
the web app (flagged, not built — see `GAPS.md`). None exist as portable
datapacks; all are raw command blocks physically placed in the world save.

### Coinflip gambling
`r.-1.0.mca`, ~`(-137 to -140, 62, 149)`. A "2 gold to play" sign gates a
`/execute store result score @p coinflip run random value 0..1` — win pays
3 gold ingots, lose pays nothing. Scoreboards: `coinflip`, `hasgold`, `bet`,
`detected`.

### The mines (4-room randomized dungeon)
Entrance ~`(-140, 66, 168)`, "Enter the mines" sign. Gated by a real
pickaxe check (`mines_lift_precheck` datapack — **already extracted and
committed** at `evoke-infra/minecraft/datapacks/mines_lift_precheck/`, though
that only covers the entry check, not the room-randomizer itself). Four
pre-built room layouts (`mine00`/`mine01`/`mine10`/`mine11`, region
`r.-1.-1.mca` ~chunks 787-825) swapped in via structure blocks, driven by a
`room00`/`room01`/`room10`/`room11` "room assign sys" state machine. Infinite
admin coal shop, auto-refilling unbreakable pickaxe.

### Minecart/dropper ride
`r.0.-1.mca`, ~`(304-306, 128-134, -142 to -144)`. A `rail1`/`cartTimer`
timer loop summons a chest minecart every 80 ticks, fed by two droppers.

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
| Critical Thinker / Foresight | Signs only, in an "admin / control room" at y=180-181 (both `true_oasis` and `unmodded`) — likely admin/testing signage, not confirmed as a live-earnable path |

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
`inventory_save`, `mines_lift_precheck` (entry check only), and
`halyard_mob_arena` (new — see §10).

**Still only raw command blocks in the world save**, not portable, not in
git: the coinflip room, the mines room-randomizer itself, the minecart ride,
the full day-job stage machine, the hidden room + parkour shaft, the
teleport hub, every badge-granting command block, and the B1llbot kiosk /
factory dialogue. If any of these ever need to survive a world rebuild or
be code-reviewed, they'd need the same extraction treatment
`mines_lift_precheck` already got.

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

## 11. Investigation tooling (currently ephemeral — not saved anywhere durable)

Built this session, stdlib-only Python (no NBT libraries were installed or
needed):

- `mca_nbt_dump.py` — raw NBT/Anvil region-file parser
- `block_at.py` — decodes the actual block palette + bit-packed section data
  to answer "what block is at world X,Y,Z" (verified against known ground
  truth before trusting it)
- `full_command_block_scan.py` — exhaustive command-block + spawner
  inventory across an entire world
- `scan_signs.py` — exhaustive sign-text inventory
- `scan_chunk_palettes.py` — fast per-chunk block-type search across a wide
  area (how the parkour shaft in §7 was actually found)

These live in this session's scratchpad
(`/private/tmp/claude-501/.../scratchpad/`), which does not persist. If
this tooling is worth keeping for future investigation (checking `unmodded`
more thoroughly, mapping the rest of Halyard/Oasis, verifying future world
edits), it should be copied into the repo — say the word and I'll do that
in a follow-up.
