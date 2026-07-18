# WHITELIST.md

## The Minecraft server has been reached by the open internet — not hypothetically, confirmed

Resolves `COMPLIANCE_TODO.md`'s P1 item **"Verify the Minecraft server isn't
publicly discoverable/joinable outside the enrolled cohort"** — the answer is
**it is, and it already has been.** This isn't a theoretical risk assessment;
it's a finding from the historical server logs at
`~/evoke-prosperity-files/minecraft/will-other-server-files/` (usercache.json,
ops.json, and `logs/*.log.gz`, decompressed and cross-referenced against
`usercache.json`'s UUIDs, real join/leave timestamps, and connecting IPs).

---

## 1. What the logs actually show

The historical server ran with `white-list=false` — no restriction on who
could connect. That setting is **still today's default**
(`evoke-infra/minecraft/server.properties.template`), unchanged. The logs
show what that default actually produces over time, not what it could in
theory produce:

- **A self-identifying scanner bot.** `KittyScan01`/`KittyScanNya`/
  `KittyScanArchive` connect from two adjacent datacenter IPs
  (`163.172.143.147`, `176.65.148.242` — OVH-range, not residential) and post
  the same canned chat message on every visit: *"Heyo o/ I am just a friendly
  bot. If you have intended for this server to be private, I urge you to add
  a whitelist to protect your server from unwanted access and potential
  griefing... See https://kittyscan.com."* This is independent, third-party
  confirmation the server was discoverable — the bot's own message is
  functionally a scan report.
- **A confirmed uninvited human.** `BoykisserFemboy` connected from a real
  residential IP (`170.9.36.20`), joined among the NPC bots, said nothing,
  and disconnected 25 seconds later. No corroborating evidence anywhere this
  is a known tester — a stranger found an open server and looked around.
- **~45 additional single-join names** with IPs scattered across the US,
  Europe, South America, and Asia — geographically inconsistent with a small
  known cohort, and with no independent corroboration (no op grant, no
  on-topic chat, no name match anywhere else in the repo/docs) that any of
  them are people associated with this project.
- **`online-mode=false`** (also still today's default) compounds this: it
  means a whitelist keyed on username string alone doesn't verify who's
  actually connecting — with auth off, anyone can claim a whitelisted name
  and be treated as that account. A whitelist is only as trustworthy as the
  identity check behind it, and today there isn't one.
- **No restriction on player-to-player chat anywhere** — checked every
  datapack currently in `evoke-infra/minecraft/datapacks/`; none touch chat.
  Vanilla Minecraft has no built-in "disable chat" setting, so this has
  never been off. Removing the B1llbot mod (`mods/billbot-2.0.0.jar`, still
  shipped in the current Dockerfile) would remove *AI* chat but does nothing
  about students — or anyone else who connects — talking to each other.

**Not confirmed one way or the other:** whether any of this happened while
real enrolled students were online at the same time. The logs prove the
server was reachable and used by non-project entities; they don't by
themselves prove a student was ever exposed to one in the same session. Given
`white-list=false` is still the default today, that's not a reassurance —
it's an open question worth treating as "assume yes until proven otherwise."

---

## 2. What was *not* done with this data, on purpose

The historical `usercache.json` has ~65 names in it. **Only six were used**
— specifically confirmed by Nathan, by real name, as actual team members —
not inferred from join counts or chat content alone, even though several
other names (repeat joins, on-topic dev chat, an `ops.json` grant) had
supporting circumstantial evidence. Bulk-whitelisting from a cache that's
already proven to contain scanner bots and at least one uninvited stranger
would defeat the point of adding a whitelist at all.

**Confirmed, ready to whitelist:**

| Username | UUID | Corroboration |
|---|---|---|
| `spicy_farkel` | `15cadcba-45d8-4120-8252-22dcd7e52f3e` | Real chat present, discussing world-building/command blocks with `Leanerdbeta6` |
| `nighthawk5554` | `85127316-825b-4303-910f-5774576a8240` | Granted op level 4 in `ops.json` |
| `capyofbara` | `e3a31d28-9fe8-43cd-abb8-6460ac69e8a2` | 22 repeat joins |
| `Clipped1` | `89ffb44c-0702-4364-85f7-c12f49639aba` | 19 repeat joins |
| `Pratul07` | `d1576f7a-3292-4882-814f-44359214548e` | 11 repeat joins |
| `hailey_looney` | `16d9e138-06f4-481b-95a4-869bb7941aa9` | Name-matches "Haily," the UI designer credited in `~/evoke-prosperity-files/uiux/haily-july-15/EVOKE-New-UI-Handoff.md` |

Also independently corroborated the same way (op-level grant + real
on-topic building chat), but not yet in the table above pending the same
direct confirmation: `mr2wei`, `blooshh`, `yuchanandrew`, `Leanerdbeta6` (also
the author of the in-world "Starter Guide" book, `MINECRAFT_WORLD_MAP.md`
§2).

All six confirmed names were checked live against Mojang's real profile API
(`api.mojang.com/users/profiles/minecraft/<name>`) — every UUID matches
`usercache.json` exactly, meaning these are genuine premium accounts, not
offline-mode hashes, and the UUIDs stay valid once `online-mode` is switched
to `true` (§3).

**Explicitly excluded, do not whitelist:**
- `KittyScan01`, `KittyScanNya`, `KittyScanArchive`, `BS_DRONE_01` — bots.
- `Jim`, `Beth`, `Benjamin`, `Craig`, `Billbot`/`BillBot` (3 separate UUIDs)
  — these are the B1llbot mod's own fake NPC player-entities, not human
  accounts.
- `BoykisserFemboy` — confirmed uninvited stranger (§1).
- Everyone else in the historical cache — no corroboration, don't assume.

### `whitelist.json` — ready to apply

```json
[
  { "uuid": "15cadcba-45d8-4120-8252-22dcd7e52f3e", "name": "spicy_farkel" },
  { "uuid": "85127316-825b-4303-910f-5774576a8240", "name": "nighthawk5554" },
  { "uuid": "e3a31d28-9fe8-43cd-abb8-6460ac69e8a2", "name": "capyofbara" },
  { "uuid": "89ffb44c-0702-4364-85f7-c12f49639aba", "name": "Clipped1" },
  { "uuid": "d1576f7a-3292-4882-814f-44359214548e", "name": "Pratul07" },
  { "uuid": "16d9e138-06f4-481b-95a4-869bb7941aa9", "name": "hailey_looney" }
]
```

Prefer applying this live via RCON (`whitelist add <name>` per entry)
over hand-editing the file on a running server — a file edit needs
`/whitelist reload` (or a restart) to take effect and is easy to leave out
of sync with what the running server actually has loaded.

---

## 3. Required config changes — not yet made

`evoke-infra/minecraft/server.properties.template`, still today's shipped
defaults:

- **`online-mode=false` → `true`.** Geyser/Floodgate is designed for this:
  Bedrock players authenticate separately via Xbox Live regardless of the
  Java server's `online-mode` setting, so this doesn't break Bedrock access
  — it just makes Java-side identity real (Mojang-verified) instead of an
  unverified claimed string, which is what makes a whitelist trustworthy at
  all. Test against the actual pinned Geyser/Floodgate/Minecraft versions
  before shipping — this project has hit real Fabric/Yarn version
  incompatibilities before (`GAPS.md`'s B1llbot-mod history).
- **`white-list=false` → `true`**, plus **`enforce-whitelist=true`** (kicks
  anyone already connected if they fall off the whitelist on reload — closes
  the gap where a stale session lingers after removal).
- **`max-players`** is already reasonable — `40` via the `MAX_PLAYERS` env
  var (`evoke-infra/docker-compose.yml`), not the unbounded `9999` the old
  historical server ran with. No change needed here.
- **Player-to-player chat has no vanilla off-switch.** Two real paths, given
  this repo already maintains a custom Fabric mod for B1llbot:
  1. Extend the existing mod with a `ServerMessageEvents.ALLOW_CHAT_MESSAGE`
     hook that cancels chat outright (or restricts it to an allowlist like
     `/trigger evoke_link`, which is a command, not chat, and is unaffected
     either way).
  2. An existing Fabric moderation mod from Modrinth — needs a real
     compatibility check against the pinned Minecraft version before
     adoption, not assumed compatible.

None of these four changes are in the current repo. `COMPLIANCE_TODO.md`'s
"Verify the Minecraft server isn't publicly discoverable/joinable" item
should move from an open verification question to a named, scoped fix once
this lands.

---

## 4. Populating the whitelist going forward

Not a one-time seed — needs to be a real, repeatable process for actual
enrolled students, not another historical-log excavation:

1. Collect each student's Minecraft username (Java) or gamertag (Bedrock) at
   the same signup/enrollment step that would already capture parental
   consent info for an extracurricular club (see the COPPA discussion this
   doc's findings came out of — school-official-exception vs. direct consent
   both need *some* enrollment step to exist).
2. Whitelist it automatically as a side effect of that enrollment, not a
   manual admin chore — `evoke-minecraft-bridge/bridge.py` already holds a
   live RCON connection, and `#/admin`'s Teams roster-import flow
   (`POST /api/admin/roster/{id}/import`) already exists. Adding a
   `minecraft_username` field to that same import step and calling
   `whitelist add <username>` over RCON at import time is a small extension
   of infrastructure that's already built, not new plumbing.
3. Keep the existing two-channel `/trigger evoke_link set <code>` flow as a
   second, independent layer on top of the whitelist — the whitelist answers
   "can this person even join," the link code answers "which real EVOKE
   student is this, for rewards/quests." With `online-mode=true`, Mojang/Xbox
   Live auth already proves account ownership, so the link code's remaining
   job is narrower (identity linkage, not possession-proof) — but it's
   already built and worth keeping regardless.

---

## 5. Not legal advice

Same caveat as `SAFETY.md` and `COMPLIANCE_TODO.md` — this is a technical
security finding and a configuration fix, not a compliance sign-off. It
directly informs `COMPLIANCE_TODO.md`'s P1 Minecraft-discoverability item and
`SAFETY.md` §1's "Minecraft chat and shared-world interaction between
learners" scope line, but doesn't replace either.
