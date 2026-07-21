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
| Stat criterion | `scoreboard objectives add <name> minecraft.<stat>` — vanilla counts it automatically (blocks mined, mobs killed, deaths, distance, crafting, trading…) | one line in a datapack `load` |
| Bridge position box | `POSITION_FLAGS` in bridge.py sets a flag when a linked player enters an area | one tuple in bridge.py |
| Bridge event | the bridge sets a flag when it processes something (a sale, a purchase, a mailbox, a balance ratchet) | a few lines in bridge.py |
| Tag mirror | bridge mirrors an entity tag into a scoreboard (`execute as @a[name=X,tag=Y] run scoreboard…`) | one line per tag |

Status legend: **LIVE** (trigger active today) · **READY** (objective
already exists in-world; only needs the quest+trigger rows) · **SMALL**
(needs one of the one-line additions above first) · *(verify)* = the
objective exists but its per-player semantics should be spot-checked
before seeding.

---

## Keel — Town

| # | Quest | Player-visible goal | Hook | Status |
|---|---|---|---|---|
| K1 | **The Overlook** | Enter the Basin | bridge presence → `basinSeen ≥ 1` | LIVE (archive) |
| K2 | **Down into Keel** | Walk down into town | bridge box → `keelVisited ≥ 1` | LIVE (archive) |
| K3 | **The Whisper** | Hear Billbot's kiosk message | tag mirror `billbot_intro` → `kioskHeard ≥ 1` | SMALL |
| K4 | **Say Hello** | Talk to one of the townsfolk | stat `minecraft.custom:minecraft.talked_to_villager ≥ 1` | SMALL |
| K5 | **Day One** | Take the free pickaxe at the worker station | world CB area → `seenMsg` *(verify semantics)* or bridge box at `(-138,63,209-212)` → `stationVisited ≥ 1` | SMALL |
| K6 | **Kitted Out** | Buy a better pickaxe at the tool store | datapack `if items` (stone/diamond pickaxe only come from the shop) → `toolBought ≥ 1` | SMALL |
| K7 | **Gambler's First Lesson** | Place a bet at the coinflip stand | world scoreboard → `bet ≥ 1` *(verify)* | READY |
| K8 | **Lucky Flip** | Win the coinflip | world CB payout → `coinflip ≥ 1` | READY |
| K9 | **Good Neighbor** | Donate at the donation bin | world CB → `kindness ≥ 1` | READY |
| K10 | **First Paycheck** | Claim wages at the mines exit | world trigger → `claimReward ≥ 1` *(verify it persists past reset-to-0)* | READY |
| K11 | **Monetary Master** | Hold 200 credits at once | world CB badge → `moneyBadgeClaimed ≥ 1` | READY |
| K12 | **Nest Egg** | Save up $250 | bridge balance ratchet (peak `bal` → `maxBalance ≥ 250`) | SMALL |
| K13 | **Ticket Holder** | Hold a train ticket | datapack `if items` paper check → `ticketHeld ≥ 1` (catches booth, trigger, and `/withdraw` alike) | SMALL |
| K14 | **The Ticket Up** | Ride the train to Halyard | bridge box → `halyardVisited ≥ 1` | LIVE (archive) |

## Keel — The Mines

| # | Quest | Player-visible goal | Hook | Status |
|---|---|---|---|---|
| M1 | **The Mines** | Find the mines entrance | bridge box → `minesVisited ≥ 1` | LIVE (archive) |
| M2 | **Rock Bottom** | Ride the lift all the way down | bridge box at room level `(-140..-95, 27..32, -122..-70)` → `mineFloorTouched ≥ 1` | SMALL |
| M3 | **First Coal** | Bring coal back up | world CBs → `gotCoal ≥ 1` | LIVE (archive) |
| M4 | **First Wages** | Sell coal to Alpha | bridge event on `sellCoal` payout → `coalSold ≥ 1` | SMALL |
| M5 | **Full Cart** | Sell 64+ coal in a single sale | bridge event (sale size) → `bigSale ≥ 1` | SMALL |
| M6 | **Deep Miner** | Mine 64 coal ore | stat `minecraft.mined:minecraft.coal_ore ≥ 64` | SMALL |
| M7 | **Stone Cold** | Mine 100 stone | stat `minecraft.mined:minecraft.stone ≥ 100` | SMALL |
| M8 | **Repairman** | Use the entrance repair station | bridge box `(-138..-134,60..63,164..168)` → `repairVisited ≥ 1` | SMALL |
| M9 | **Curious** | Open a chest in the Basin | stat `minecraft.custom:minecraft.open_chest ≥ 1` | SMALL |

## Keel — Secrets & Heights

| # | Quest | Player-visible goal | Hook | Status |
|---|---|---|---|---|
| S1 | **Secret Finder** | Discover the hidden room | bridge box `(75-82,62-67,145-154)` → `hiddenRoomFound ≥ 1` | SMALL |
| S2 | **Climber** | Climb 50m of scaffolding and ladders | stat `minecraft.custom:minecraft.climb_one_cm ≥ 5000` | SMALL |
| S3 | **Summit of Keel** | Reach the prismarine ring atop the parkour shaft | bridge box `(-16..2,117..122,93..121)` → `parkourTopped ≥ 1` | SMALL — *finally gives the parkour its missing reward* |
| S4 | **Clean Slate** | Find and use the old Alpha terminal | bridge event on `balanceWipe` → `terminalUsed ≥ 1` | SMALL |
| S5 | **Storm Caller** | Perform the diamond ritual | one added line in `basin_secrets:tick` tags nearby players before the strike → `stormCalled ≥ 1` | SMALL |

## Halyard

| # | Quest | Player-visible goal | Hook | Status |
|---|---|---|---|---|
| H1 | **New Address** | Arrive in Halyard | bridge box → `halyardVisited ≥ 1` (shared with K14) | LIVE (archive) |
| H2 | **Clocked In** | Start a shift at the day job | world machine → `stage ≥ 1` | READY |
| H3 | **Model Employee** | Work the full day-job cycle | world machine → `stage ≥ 5` *(verify top stage)* | READY |
| H4 | **Rent Day** | Pay your rent on time | world/datapack → `rentPaid ≥ 1` | READY (retitle the mis-labeled "Factory Crafting I" row) |
| H5 | **Hard Lesson** | Get hit with a late fee | world scoreboard → `late ≥ 1` *(verify per-player)* | READY |
| H6 | **Saving Up** | Bank 30 levels of factory time | `xpLevel ≥ 30` | READY |
| H7 | **Time Saver** | Bank the full 60 levels | `xpLevel ≥ 60` | READY |
| H8 | **Factory Shift** | Work the crafting factory floor | bridge box `(295-333,118-134,-154..-111)` → `factoryVisited ≥ 1` | SMALL |
| H9 | **Foreign Exchange** | Trade emeralds with a factory villager | stat `minecraft.custom:minecraft.traded_with_villager ≥ 1` | SMALL |
| H10 | **Line Worker** | Craft a bookshelf from factory materials | stat `minecraft.crafted:minecraft.bookshelf ≥ 1` | SMALL |
| H11 | **Master Fabricator** | Craft the beacon | stat `minecraft.crafted:minecraft.beacon ≥ 1` | SMALL |
| H12 | **Rail Rider** | Ride the minecart line 100m | stat `minecraft.custom:minecraft.minecart_one_cm ≥ 10000` | SMALL |
| H13 | **Eavesdropper** | Overhear Billbot at the geothermal factory | world CB scene → `halyardFactoryDialoguePlayed ≥ 1` *(verify per-player)* | READY |
| H14 | **Gladiator** | Survive wave 1 of the Mob Arena | datapack → `arenaBestWave ≥ 1` | READY |
| H15 | **Arena Champion** | Clear all 5 arena waves | `arenaBestWave ≥ 5` | READY |
| H16 | **No Guts, No Glory** | Fall in the arena (and come back) | datapack → `arenaDeaths ≥ 1` | READY |
| H17 | **Exterminator** | Kill 10 arena spiders | stat `minecraft.killed:minecraft.spider ≥ 10` | SMALL |
| H18 | **Bruiser** | Deal 1,000 damage to Basin mobs | stat `minecraft.custom:minecraft.damage_dealt ≥ 10000` (tenths) | SMALL |
| H19 | **Brothers in Arms** | Survive a Gauntlet wave with your crew | datapack → `gauntletBestWave ≥ 1` | READY |
| H20 | **Giant Slayer** | Beat the Gauntlet's final wave | `gauntletBestWave ≥ 7` | READY |
| H21 | **Credentialed** | Obtain the Name Tag credential | datapack `if items` name_tag check → `credentialHeld ≥ 1` | SMALL |

## Oasis

| # | Quest | Player-visible goal | Hook | Status |
|---|---|---|---|---|
| O1 | **The Ascent** | Ride the lift to the Oasis | bridge box at `(57,149,1095)`± → `oasisVisited ≥ 1` | SMALL |
| O2 | **Settled** | Receive your settlement stipend | mailbox already advances → `stipendDue ≥ 2` | READY |
| O3 | **The View** | Take in the summit overlook | bridge box at `(58,135,1000)`± → `overlookVisited ≥ 1` | SMALL |
| O4 | **Surveyor** | Walk the unclaimed plots | bridge box at `(756,131,-367)`± → `plotsVisited ≥ 1` | SMALL |
| O5 | **First Foundation** | Place a crafting table in the open world | stat `minecraft.used:minecraft.crafting_table ≥ 1` | SMALL |
| O6 | **Lumberjack** | Fell 20 logs for your build | stat `minecraft.mined:minecraft.oak_log ≥ 20` | SMALL |
| O7 | **Groundbreaker** | Clear 100 dirt for a foundation | stat `minecraft.mined:minecraft.dirt ≥ 100` | SMALL |

## Anywhere in the Basin

| # | Quest | Player-visible goal | Hook | Status |
|---|---|---|---|---|
| A1 | **Death & Taxes** | Die once (it happens) | stat criterion `deathCount ≥ 1` | SMALL |
| A2 | **Marathoner** | Walk 10 km across the Basin | stat `minecraft.custom:minecraft.walk_one_cm ≥ 1,000,000` | SMALL |
| A3 | **Sprinter** | Sprint a full kilometer | stat `minecraft.custom:minecraft.sprint_one_cm ≥ 100,000` | SMALL |
| A4 | **Water Is Life** | Swim 100m in the Basin's waters | stat `minecraft.custom:minecraft.swim_one_cm ≥ 10,000` | SMALL — *the title is the campaign's thesis* |
| A5 | **Rations** | Eat bread like a Keel worker | stat `minecraft.used:minecraft.bread ≥ 1` | SMALL |
| A6 | **Resident** | Spend an hour in the Basin | stat `minecraft.custom:minecraft.play_time ≥ 72,000` (ticks) | SMALL |
| A7 | **Citizen of the Basin** | Spend five hours in the Basin | stat `minecraft.custom:minecraft.play_time ≥ 360,000` | SMALL |
| A8 | **Frequent Flyer** | Take 1,000 jumps | stat `minecraft.custom:minecraft.jump ≥ 1,000` | SMALL |

---

## Wiring notes

- **Adding any quest** = one `mc_quests` row (`kind='side_quest'` unless it
  joins the Basin Archive narrative) + one `mc_quest_triggers` row, seeded
  in main.py's startup block. SMALL items also need their one-line
  detector (datapack criterion / bridge box / bridge event) — all patterns
  documented in `MINECRAFT_GAME_REFERENCE.md` §8. Stat-criterion
  objectives all go in one datapack `load` function (`basin_qol` is the
  natural home).
- **Detection only works for linked players** (`quest_trigger_loop` joins
  through `minecraft_links`); stat criteria still count beforehand, so a
  player who links late completes retroactively on the next pass.
- **Tiering**: where a stat has two thresholds (Saving Up / Time Saver,
  Resident / Citizen, Gladiator / Arena Champion, Brothers in Arms /
  Giant Slayer) each tier is just a second quest row on the same
  objective with a higher threshold — the pipeline handles it natively.
- ***(verify)* items**: `bet`, `late`, `seenMsg`, `claimReward`
  persistence, `stage` top value, and `halyardFactoryDialoguePlayed` are
  world scoreboards whose per-player semantics were read from command
  blocks, not play-tested — set the score on a test account and watch
  `quest_trigger_loop` before seeding those five.
- **Surfacing**: the Basin Archive (6 memories) stays the curated
  narrative chain on the tablet. This catalog needs its own lighter
  surface — a "Quest Log" checklist on the Simulator tab (name + ✓), fed
  by the same `/api/mc-quests` + completions data. Not yet built.
- **DB cleanup owed**: every `mission_quest`/`side_quest` row is
  triplicated (an old seeding bug — visible via
  `SELECT title, count(*) FROM mc_quests GROUP BY title`), and the
  `rentPaid` trigger sits on the mis-titled "Factory Crafting I". Fix both
  before wiring the new rows.
- The legacy no-trigger rows ("Explorer's Log", "Find Hidden Treasure",
  "Master Farmer", "Mining Expert", and the 12 mission-titled quests)
  predate the separation rule — retire or absorb them into this catalog
  rather than leaving three parallel quest vocabularies.
