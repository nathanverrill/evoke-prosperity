# Vision Phase → Lived Phase: implementation plan

## The design (confirmed this session)

Two shared, world-scoped phases, toggled by one flag — not tied to any web-app event, so it's trivially testable by flipping a command:

- **Vision phase** (`vision_phase = 1`): everyone has flight (`mayfly`). This is the "this is what it was" beat — players fly freely over Keel/Halyard/Oasis and take in the whole world before anything constrains them. NPCs are silent: nobody can see or hear you (echoes Billbot's own kiosk line, "no one else in this city can see this kiosk"). No response at all when you talk to them — matches "you're not really here yet."
- **Lived phase** (`vision_phase = 0`): flight revoked. Players are grounded and can only get around the way the world already makes you — walking, and the existing self-contained Minecraft economy (mine coal → sell to Alpha → save → buy a ticket → progress toward Halyard/Oasis). NPCs respond normally — the moment you're first spoken to and seen is the mechanical payoff of "now you live it, you walk in his shoes." Directly reinforces the Empathy mission content, not just narrated.
- **Constant across both phases**: Adventure mode, permanently. Nobody can ever break or place a block, in either phase. This is non-negotiable per the "no one is supposed to be able to destroy the environment, ever" requirement — it's why the *existing* `gamemode_lock` datapack (built earlier this session, commit `cca15ba`) is wrong and gets replaced, not deployed: it assumed a Survival→Adventure transition, and Survival allows destruction.
- **The minigames themselves are untouched.** Mining, the mob arena, the crafting factory, minecart rides, coinflip — all already self-contained, gated only by in-game money/tickets, exactly as the cu-internship docs describe. No new gating code needed there; the "lock" is entirely about flight + NPC access, not about re-implementing progression that already works.

## Known real bug to fix as part of this, unrelated to the toggle itself

The live `server.properties` on Apex currently has `gamemode=creative` + `force-gamemode=true` (found in the recovered reference config, confirmed this is what actually got delivered). That's the opposite of the "always Adventure" baseline this design requires — needs correcting regardless of when the toggle work happens.

## Pieces to build

### 1. Minecraft: replace `gamemode_lock` datapack
- `evoke-infra/minecraft/datapacks/gamemode_lock/` already exists but is wrong (Survival↔Adventure premise) — rewrite it, don't just deploy as-is.
- New scoreboard objective, e.g. `vision_phase` (not `missions_locked`), `#global` holder, defaulting to `1` (vision phase) on world load — matches "starts wide open."
- `tick.mcfunction`: `execute if score #global vision_phase matches 1 as @a run effect give @s minecraft:... ` — actually flight isn't an effect, it's an ability. Need `/data merge entity @s {abilities:{mayfly:1b}}` while `vision_phase=1`, and `{abilities:{mayfly:0b,flying:0b}}` while `0`, applied every tick to catch new joiners (same pattern as the original tick-gated enforcement, just targeting the ability NBT instead of gamemode).
- Gamemode itself: set once at `load` (everyone Adventure) and re-enforced every tick regardless of phase (`execute as @a[gamemode=!adventure] run gamemode adventure @s`) — this is the part that's now unconditional, not phase-gated.
- Toggle mechanism: a simple `/scoreboard players set #global vision_phase 0` (or `1`) run by an admin — via command, or a physical lever/button wired the same way the tphub's existing sign+command-block pattern works, whichever's more convenient for testing. No `bridge.py`/event dependency for the flip itself, per your explicit ask.

### 2. Minecraft: gate the multi-NPC billbot mod on the same flag
- `BillBot.java`'s chat listener needs to read `vision_phase` before responding. Simplest approach: RCON-readable scoreboard is server-side state the *datapack* owns; the Java mod would need its own way to check it — either (a) the mod reads the same scoreboard value via the server's scoreboard API directly (`server.getScoreboard()...`), avoiding any cross-system sync issue, or (b) the datapack also writes a tiny world-state marker the mod polls. (a) is cleaner — no double-source-of-truth.
- While silent: `return true` (let the raw chat message pass through unmodified, no `[Name]` reply) instead of the current unconditional intercept-and-respond — reinforces "nobody's listening" rather than showing an obvious "NPC muted" message.

### 3. Apex config fix
- Correct `server.properties`: `gamemode=adventure`, `force-gamemode=true` stays (good — it's what *enforces* the always-Adventure rule at the server level too, belt-and-suspenders with the datapack's tick enforcement).

### 4. Web app: Companion Mode / Field Kit nudge
- New, real scope beyond the Minecraft-side mechanic. `bridge.py` already holds an RCON connection — add a watcher that reads `vision_phase` (polling, same pattern as its other RCON polling loops) and detects the 1→0 transition.
- On transition: either publish a new event (matching the existing `WorldStateAdvanced`/`MissionCompleted` pattern the web app's event pipeline already consumes) or expose a small new endpoint (`GET /api/minecraft/phase`) that `companion.html` checks on load/poll.
- `companion.html`: new nudge banner — "go talk to Jim, Beth, Benjamin, Craig, and Billbot" — shown once the lived phase begins. Exact copy/placement is a design call, not scoped further here.

## Explicitly out of scope for this pass
- Any change to the minigames' internal economy/progression logic — confirmed already correct and self-contained.
- Any web-app mission-completion event triggering the phase flip — explicitly rejected in favor of a standalone toggle, for testing.
- Deciding the exact nudge banner copy/design in Companion Mode — flagged as a real piece, not pre-designed here.

## Update 2026-07-17: pivoted to a two-server design, then paused for the playtest

After the single-server (`vision_phase` scoreboard flag) version above was built,
tested, and confirmed working locally, the conversation moved toward a
different, more isolated design -- captured here so the work already done
isn't lost, even though it's now paused in favor of simpler playtest prep
(see bottom of this section).

**Why the pivot**: extending the single-server flag to also block the
minigames (not just NPCs) would mean editing 6+ already-working datapacks
I didn't build and hadn't re-verified fresh -- real regression risk against
systems that currently just work (we'd already seen tonight how one
malformed datapack folder can crash an entire server). A second, genuinely
separate server sidesteps that entirely: no risk of touching working
minigame code, since the minigames just aren't there at all.

**The two-server design**:
- **`sim.apexmc.co`** -- the vision phase. Stripped to just the world +
  Adventure mode + universal flight. No NPCs, no minigames, no mods beyond
  whatever's needed for connectivity.
- **`prosperity.apexmc.co`** -- the real, as-designed server (this is the
  same server referenced throughout this session as the main Apex
  instance, `6689.node.apexhosting.gdn` -- `prosperity.apexmc.co` is
  Apex's custom-domain alias for it).
- **Transfer mechanism**: Minecraft's built-in `/transfer <host> <port>`
  command (added 1.20.5, no proxy/BungeeCord needed) -- fired server-side
  to move a specific player from `sim` to `prosperity` seamlessly, no
  manual reconnect. Proposed trigger: the same admin action that would
  have flipped `vision_phase` to 0 also fires the transfer for everyone
  online, so "stop flying, go silent, leave this server" happens as one
  event instead of three things to keep in sync.
- **Players manually reconnecting to `sim` later** (after already having
  moved to `prosperity`): decided this needs no special handling. `sim`
  has no economy/inventory/mission state, so there's nothing to
  duplicate or exploit by revisiting -- narratively it reads fine too
  ("revisiting a memory" vs. "living it twice"). Not building any
  return-visitor blocking logic.

**What was actually found/done on `sim.apexmc.co` before pausing**:
- FTP username is per-server, not shared with `prosperity` -- had to get
  `sim`'s own username (`nathanverrill@gmail.com.3151410`) from the panel;
  same account password worked once we had the right username.
- `sim` turned out to already have a real, substantial `true_oasis` world
  (region data, 1.7KB `level.dat` -- not a stub) uploaded the same day,
  plus the **full original mod stack**, more complete than anything
  pieced together on `prosperity` tonight: `BiomesOPlenty`, `GlitchCore`,
  `TerraBlender`, `chisels-and-bits`, `fabric-api-0.138.4+1.21.10`, `JEI`,
  `polyfactory`, `polymer-bundled`, **`savs-common-economy`** (the actual
  shop-system mod -- would make the "Admin Shop" signs found earlier this
  session actually functional, something never achieved on `prosperity`),
  `thirdbrain-1.21.10-v4.0.1-alpha` (newer than the v4.0.0 built earlier
  tonight), `worldedit-mod`. Worth remembering this exists next time
  `prosperity`'s missing shop/decoration mods come up.
- All 11 mods moved (not deleted) to `/default/mods-backup-full-stack/` on
  `sim` -- recoverable, not gone.
- A new `sim_vision` datapack was built and uploaded to
  `true_oasis/datapacks/sim_vision/` on `sim`: unconditional
  Adventure-mode enforcement (only corrects players actually in Survival,
  so an admin can still deliberately use Creative) + universal `mayfly`
  grant every tick. No toggle needed on this server -- it's permanently
  the vision experience; leaving it happens via the transfer, not a mode
  change.
- **Not yet done**: `server.properties` on `sim` still says
  `gamemode=creative` (needs to become `adventure` for the datapack's
  enforcement to matter -- right now Creative would just override it
  every tick, though harmlessly). Server hasn't been restarted since the
  mod removal + datapack upload, so none of this is live yet.
- **Real open question surfaced, not resolved**: `sim` never had
  Geyser/Floodgate installed at all (they weren't among the 11 mods
  removed) -- Bedrock players currently cannot connect to `sim` at all,
  a hard protocol wall, not a soft limitation. If the vision phase is
  meant to be every player's first experience (matching `prosperity`'s
  existing Java+Bedrock support via Geyser/Floodgate), this needs
  Geyser-Fabric + Floodgate-Fabric added back (~15MB, small next to the
  90MB of mods that were removed) before `sim` is usable by Bedrock
  players. Left undecided when the session pivoted away from this thread.

**Paused here.** For the actual near-term playtest, the priority shifted
to writing clear, in-narrative help/guidance text for the Field Kit /
Companion Mode page instead of finishing the two-server infrastructure.
The single-server `vision_phase` version earlier in this doc is still
built, tested, and working if a simpler path is wanted later instead of
finishing the two-server approach.

## Verification
- Toggle `vision_phase` via RCON directly, confirm: all online players get/lose `mayfly` within one tick; nobody can break/place blocks in either state; NPC chat is silent vs. responsive matching the flag.
- Confirm the old `gamemode_lock` datapack is fully removed/replaced, not left deployed alongside the new one (would double-fire conflicting logic).
- Confirm `server.properties` fix survives a restart (`gamemode=adventure` persists, isn't reset by some other process).
- Manually flip the flag, confirm `bridge.py` detects the transition and the Companion Mode nudge appears within one poll cycle.
