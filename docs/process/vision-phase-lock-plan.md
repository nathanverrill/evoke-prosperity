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

## Verification
- Toggle `vision_phase` via RCON directly, confirm: all online players get/lose `mayfly` within one tick; nobody can break/place blocks in either state; NPC chat is silent vs. responsive matching the flag.
- Confirm the old `gamemode_lock` datapack is fully removed/replaced, not left deployed alongside the new one (would double-fire conflicting logic).
- Confirm `server.properties` fix survives a restart (`gamemode=adventure` persists, isn't reset by some other process).
- Manually flip the flag, confirm `bridge.py` detects the transition and the Companion Mode nudge appears within one poll cycle.
