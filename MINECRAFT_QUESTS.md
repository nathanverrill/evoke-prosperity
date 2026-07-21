# MINECRAFT_QUESTS.md — the auto-completing quest catalog

**Quests are Minecraft-only.** Missions are school assignments (Brightspace,
graded) and never touch this list — see the mission-vs-quest separation
rule. A quest is something the world *detects the player doing*: no
self-reporting, no grading, no gating. Completion flows through the
existing pipeline (`mc_quest_triggers` → bridge `quest_trigger_loop` →
`QuestCompleted` + XP + in-game tellraw + tablet), which means **every
quest below is defined by one scoreboard objective and a threshold** —
that's the whole hook.

Hook mechanisms available (see `MINECRAFT_GAME_REFERENCE.md` §7–8):

| Mechanism | How it works | Cost to add |
|---|---|---|
| World scoreboard | a command block / datapack already sets it | zero — just seed the trigger row |
| Stat criterion | `scoreboard objectives add <name> minecraft.<stat>` — vanilla counts it automatically (blocks mined, mobs killed, deaths, distance…) | one line in a datapack `load` |
| Bridge position box | `POSITION_FLAGS` in bridge.py sets a flag when a linked player enters an area | one tuple in bridge.py |
| Bridge event | the bridge sets a flag when it processes something (a sale, a purchase, a mailbox) | a few lines in bridge.py |
| Tag mirror | bridge mirrors an entity tag into a scoreboard (`execute as @a[name=X,tag=Y] run scoreboard…`) | one line per tag |

Status legend: **LIVE** (trigger active today) · **READY** (objective
already exists in-world; only needs the quest+trigger rows) · **SMALL**
(needs one of the one-line additions above first).

---

## Act 1 — Keel

| # | Quest | Player-visible goal | Hook | Status |
|---|---|---|---|---|
| 1 | **The Overlook** | Enter the Basin | bridge presence → `basinSeen ≥ 1` | LIVE (archive) |
| 2 | **Down into Keel** | Walk down into town | bridge box → `keelVisited ≥ 1` | LIVE (archive) |
| 3 | **The Whisper** | Hear Billbot's kiosk message | tag mirror `billbot_intro` → `kioskHeard ≥ 1` | SMALL |
| 4 | **The Mines** | Find the mines entrance | bridge box → `minesVisited ≥ 1` | LIVE (archive) |
| 5 | **First Coal** | Bring coal back up | world CBs → `gotCoal ≥ 1` | LIVE (archive) |
| 6 | **First Wages** | Sell coal to Alpha | bridge event on `sellCoal` payout → `coalSold ≥ 1` | SMALL |
| 7 | **Deep Miner** | Mine 64 coal ore | stat `minecraft.mined:minecraft.coal_ore` → `coalOreMined ≥ 64` | SMALL |
| 8 | **Kitted Out** | Buy a better pickaxe at the tool store | datapack `if items` inventory check (stone/diamond pickaxe only come from the shop) → `toolBought ≥ 1` | SMALL |
| 9 | **Lucky Flip** | Try the coinflip stand | world scoreboard → `coinflip ≥ 1` | READY |
| 10 | **Good Neighbor** | Donate at the donation bin | world CB → `kindness ≥ 1` | READY |
| 11 | **Secret Finder** | Discover the hidden room | bridge box `(75-82,62-67,145-154)` → `hiddenRoomFound ≥ 1` | SMALL |
| 12 | **Summit of Keel** | Reach the prismarine ring atop the parkour shaft | bridge box `(-16..2,117..122,93..121)` → `parkourTopped ≥ 1` | SMALL — *finally gives the parkour its missing reward* |
| 13 | **Ticket Holder** | Hold a train ticket | datapack `if items` paper check → `ticketHeld ≥ 1` (catches booth, `/trigger buyTicket`, and `/withdraw` purchases alike) | SMALL |
| 14 | **The Ticket Up** | Ride the train to Halyard | bridge box → `halyardVisited ≥ 1` | LIVE (archive) |

## Act 2 — Halyard

| # | Quest | Player-visible goal | Hook | Status |
|---|---|---|---|---|
| 15 | **Clocked In** | Start a shift at the day job | world machine → `stage ≥ 1` | READY |
| 16 | **Rent Day** | Pay your rent on time | world/datapack → `rentPaid ≥ 1` | READY (currently mis-titled "Factory Crafting I" in the DB — retitle) |
| 17 | **Time Saver** | Bank 60 levels of factory time | `xpLevel ≥ 60` (level criterion, live) | READY |
| 18 | **Factory Shift** | Work the crafting factory floor | bridge box `(295-333,118-134,-154..-111)` → `factoryVisited ≥ 1` | SMALL |
| 19 | **Gladiator** | Survive wave 1 of the Mob Arena | datapack → `arenaBestWave ≥ 1` | READY |
| 20 | **Arena Champion** | Clear all 5 arena waves | `arenaBestWave ≥ 5` | READY |
| 21 | **Brothers in Arms** | Survive a Gauntlet wave with your crew | datapack → `gauntletBestWave ≥ 1` | READY |
| 22 | **Giant Slayer** | Beat the Gauntlet's final wave | `gauntletBestWave ≥ 7` | READY |
| 23 | **Exterminator** | Kill 10 arena spiders | stat `minecraft.killed:minecraft.spider` → `spidersKilled ≥ 10` | SMALL |
| 24 | **Credentialed** | Obtain the Name Tag credential | datapack `if items` name_tag check → `credentialHeld ≥ 1` | SMALL |

## Act 3 — Oasis

| # | Quest | Player-visible goal | Hook | Status |
|---|---|---|---|---|
| 25 | **The Ascent** | Ride the lift to the Oasis | bridge box at `(57,149,1095)`± → `oasisVisited ≥ 1` | SMALL |
| 26 | **Settled** | Receive your settlement stipend | mailbox already advances → `stipendDue ≥ 2` | READY |
| 27 | **First Foundation** | Place a crafting table in the open world | stat `minecraft.used:minecraft.crafting_table` → `foundationPlaced ≥ 1` | SMALL — the build-system starter |

## Side quests (any time)

| # | Quest | Player-visible goal | Hook | Status |
|---|---|---|---|---|
| 28 | **Storm Caller** | Perform the diamond ritual | one added line in `basin_secrets:tick` tags nearby players before the strike → `stormCalled ≥ 1` | SMALL |
| 29 | **Clean Slate** | Find and use the old Alpha terminal | bridge event on `balanceWipe` → `terminalUsed ≥ 1` | SMALL |
| 30 | **Death & Taxes** | Die once (it happens) | stat criterion `deathCount ≥ 1` | SMALL |
| 31 | **Marathoner** | Walk 10 km across the Basin | stat `minecraft.custom:minecraft.walk_one_cm ≥ 1,000,000` | SMALL |

---

## Wiring notes

- **Adding any quest** = one `mc_quests` row (`kind='side_quest'` unless it
  joins the Basin Archive narrative) + one `mc_quest_triggers` row, seeded
  in main.py's startup block. SMALL items also need their one-line
  detector (datapack criterion / bridge box / bridge event) — all patterns
  documented in `MINECRAFT_GAME_REFERENCE.md` §8.
- **Detection only works for linked players** (`quest_trigger_loop` joins
  through `minecraft_links`); stat criteria still count beforehand, so a
  player who links late completes retroactively on the next pass.
- **Surfacing**: the Basin Archive (6 memories) stays the curated
  narrative chain on the tablet. This longer catalog needs its own
  lighter surface — e.g. a "Quest Log" list on the Simulator tab showing
  name + ✓, fed by the same `/api/mc-quests` + completions data. Not yet
  built.
- **DB cleanup owed**: every `mission_quest`/`side_quest` row is
  triplicated (an old seeding bug — visible via
  `SELECT title, count(*) FROM mc_quests GROUP BY title`), and the
  `rentPaid` trigger sits on the mis-titled "Factory Crafting I". Fix both
  before wiring the new rows.
- The legacy no-trigger rows ("Explorer's Log", "Find Hidden Treasure",
  "Master Farmer", "Mining Expert", and the 12 mission-titled quests)
  predate the separation rule — retire or absorb them into this catalog
  rather than leaving three parallel quest vocabularies.
