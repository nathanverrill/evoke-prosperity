# MINECRAFT_REWARDS.md — web-mission rewards that land in the Basin

The transmedia direction opposite to quests: **quests** are Minecraft acts
the web notices; **rewards** are web achievements (mission completions,
award tiers, level-ups) made physical in Minecraft. The pipeline already
exists end-to-end — `RewardCollected` events → bridge → `mc_reward_catalog`
tier lookup → RCON delivery with offline queueing (`mc_reward_grants`) —
so everything here is catalog content + small delivery polish, not new
architecture.

## Why the current catalog fails

(`mc_reward_catalog` today, per tier, rows duplicated 4×:)

- `common` = **64 dirt or 1 stone** — a student completes a graded mission
  and the game hands them dirt. Worse than nothing.
- `epic`/`legendary` = **diamond/netherite pickaxes, 8 diamonds, enchanted
  golden apple** — these *break the game's own economy*: the mines'
  pickaxe-tier progression, the coal wage loop, and the arenas' difficulty
  are all trivialized by a free super-tool. Now that survival building is
  live outside town, a netherite pickaxe is even more distorting.
- Delivery is **silent** — the item appears in inventory with no
  announcement, so the reward doesn't even register as a reward.

## Principles for meaningful rewards

1. **Identity beats utility.** A trophy that names the student's
   achievement (lore text, custom names, a companion) is remembered; a
   consumable buff is not. Cosmetic/identity rewards also can't unbalance
   anything.
2. **Utility must be bounded.** Timed effects (minutes, not permanent) and
   consumables that feed the *existing* loops (a train ticket, emeralds
   for the factory) are fine; permanent tools/armor that skip loops are
   not.
3. **Economy grants stay small** relative to earned income ($1/coal;
   ticket $100): a mission bonus of $10–50 accelerates without replacing
   labor.
4. **Every delivery announces itself** — tellraw + sound at minimum;
   legendary gets spectacle.
5. Rewards **never gate** anything, same as quests.

## Proposed tier catalog

| Tier (web source) | Reward set | Exact mechanism |
|---|---|---|
| `common` (evidence submitted) | **Commendation** — a written book signed by B1llbot naming the mission + $10 + 10 min Haste I ("Alpha work permit") | `give` written book (title = mission name — needs the bridge to template it from event data); `givemoney` via bridge; `effect give <p> haste 600 0` |
| `rare` | **Courier package** — Speed II 15 min + a train ticket voucher (1 paper) + $20 | `effect`, `give paper 1`, `givemoney` |
| `epic` (AI review passed) | **Guild Standing** — Hero of the Village 30 min (**real economy meaning: factory villager trade discounts**) + a named trophy item with lore ("For excellence in Mission N") + $30 | `effect give <p> minecraft:hero_of_the_village 1800 0`; `give` any base item with `custom_name` + `lore` components |
| `legendary` (capstone/Evokation) | **The Allay Companion** — a named, persistent allay that follows the player (an Alpha Dynamics "courier drone," Billbot's kin) + a personal firework show + glowing 10 min + $50 | `summon allay` at player with `CustomName`, `PersistenceRequired`; 3× `summon firework_rocket` staggered; `effect give <p> glowing 600` |
| `kit` (Aqueduct Kit complete) | conduit trophy (unchanged — already thematic: "the most water-alive block in the game") | existing |
| `checkin` (daily) | compass (fine) + consider rotating poppy/torch/bread from `ambient` | existing |
| level-ups | title + sound + totem particles (already live, keep) | existing bridge handler |

## The wider idea list (pull from here as tiers evolve)

**Identity / trophy (zero balance impact):**
- Mission commendation books, one per mission, signed "B1llbot" — a
  collectible shelf of your semester
- Named + lored trophy items (an "Iron Resolve" ingot; a "First Ascent"
  prismarine shard) — any base item becomes a trophy via components
- The player's own head (`give <p> minecraft:player_head[profile=<p>]`) at
  capstone — the classic "you made it" trophy
- Agent Sigil banner: a banner whose patterns/colors are derived from the
  web app's sigil config — the strongest identity bridge (needs a small
  color→pattern mapping in the bridge)
- A personal firework salute at the kiosk next time they stand near it
  (delayed spectacle: bridge fires when presence box hits)
- Glowing effect ("commendation aura") — visible status to other players

**Bounded utility:**
- Haste ("work permit"), Speed ("courier boots"), Night Vision ("miner's
  lamp" — the mines are dark), Water Breathing ("Water Is Life blessing"),
  Absorption hearts before an arena run ("Guild insurance")
- Hero of the Village — the sleeper hit: it *mechanically* discounts the
  factory villagers' emerald trades, so a web achievement briefly makes
  the in-game economy kinder. Perfectly on-theme.
- An Ender Chest (`give`) — private storage, real utility, no combat/
  economy distortion

**Bounded economy:**
- $10/$20/$30/$50 by tier (`givemoney` — must go through the bridge, mod
  commands can't run from datapacks)
- A small emerald packet (2–4) — feeds the factory loop without skipping it
- One train ticket (paper) — "travel voucher," saves one grind cycle, not
  the skill
- NOT a Name Tag credential — that's the Act 2 capstone; gifting it
  deletes a whole act

**Cohort-level (already live, listed for completeness):**
- Keel Restoration Beacon growth per world stage; Team Wheel and mission
  broadcasts; ambient lore lines

## Implementation notes

- **Reward sets need multi-command delivery**: today the bridge picks one
  catalog row per tier (`LIMIT 1`). Either (a) deliver *all* rows for the
  tier (small `deliver_reward` loop change — rows become the set), or
  (b) make each tier one `command` row pointing at a bridge-side set.
  Option (a) is least code and keeps the catalog data-driven.
- **`givemoney`/mod commands work over RCON** (bridge) but never in
  datapack functions — same mailbox rule as everywhere
  (`MINECRAFT_GAME_REFERENCE.md` §9).
- **Announce on delivery**: add a tellraw + `playsound
  minecraft:entity.player.levelup` to `deliver_reward`, and for legendary
  a title. One function, all tiers benefit.
- **Mission-specific book text** needs `RewardCollected` to carry the
  mission title (it already carries `mission_id` — one lookup in the
  bridge).
- **Catalog cleanup owed**: dedupe the 4× rows (same seeding bug family as
  `mc_quests`), and remove the economy-breaking items (diamond/netherite
  pickaxes, enchanted golden apple) when the new sets land.
- The allay: `PersistenceRequired:1b` + name; allays follow the player
  holding nothing special and are immune to most harm — verify behavior
  on 1.21.11 with one spawn before shipping legendary.
