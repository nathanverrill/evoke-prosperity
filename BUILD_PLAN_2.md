# BUILD_PLAN_2.md — Wave 3: "What Done Means"

Nathan's design questions (July 13), answered, with a scoped build plan.
Companion to the original `BUILD_PLAN.md` (historical) and `GAPS.md`
(live status). Nothing here is built yet — this is the plan.

---

## 1. The diagnosis: navigation & order of importance

**The problem is real and it's an altitude problem.** The current nav
offers six coequal destinations (Hub / Novel / Gallery / Training /
Dossier / B1llbot) with no hierarchy, and the Hub leads with the *cohort's*
world meter — emotionally the right flag, but it answers "how are WE
doing" before the learner's actual first question, **"what should I do
right now?"**

**Principle to adopt: order screens by the learner's questions, not our
features.**

1. *What do I do now?* → one primary action, top-left, always.
2. *Where am I in the whole thing — what does done mean?* → the Campaign
   Map (§2, new).
3. *What's happening around me?* → feed/cohort, below personal.
4. *What else is there?* → optional layers (Basin, Training, Novel),
   clearly marked optional.

**Nav restructure (proposal):**

| Now | Becomes | Why |
|---|---|---|
| Operations Hub | **Now** (home) | Reordered: Next Action card first; compact world-state strip moves under the topbar as a one-line banner (glanceable pride, not a roadblock) |
| — (new) | **Campaign Map** | The "what done means" infographic, §2 — the missing #2 question |
| Novel, Gallery | **Story** and **Cohort** | Renamed by function; Gallery is the social surface, say so |
| Training, Basin cards | **Field Ops** (one section) | Both are the optional layer; Basin content appears only after linking (§4) |
| Dossier | **Dossier** (unchanged) | Identity/loadout answers "who am I," distinct from "where am I" |
| B1llbot nav item | drop from nav | He's a *presence* (persistent drawer + full-screen mode from the drawer), not a place |

---

## 2. The "what done means" infographic: the Campaign Map

One concise, glanceable answer to "what is the whole experience and what
counts as done," rendered as **the Basin's water pipeline**: 6 stage
nodes (one per campaign week / release stage) connected by a pipe that
visibly fills as the cohort's learner completes stages — the same
water-rises language as everything else.

**Per stage node (concise — one ring + one letter grade):**
- **Completion ring** — % of that stage's missions submitted. 100% = ring
  closes, node lights, pipe segment fills.
- **Quality grade** — the *best-tier* aggregate across the stage's
  missions: all legendary = ★★★, all ≥ epic = ★★, all submitted = ★.
  This is where revise-and-resubmit pays off visibly: resubmitting to
  upgrade a tier upgrades the stage grade.
- **Attached, smaller:** chapter unlock state, and (only if
  Minecraft-linked, §4) the stage's Basin quest state.

**"Done" legend (the infographic's key, verbatim on screen):**
> Submitted = the mission counts (common). AI-strengthened = epic.
> Teacher-honored = legendary. A stage is DONE at 100% submitted;
> its GRADE is how you did it. Quests and Training never gate anything —
> they're how agents get sharper.

**Build:** `GET /api/progress-map/{user_id}` composes per-stage rollups
from existing tables/projections (no new events). New screen `#/map` +
a compact horizontal variant embedded at the top of Now and the Field Kit.

**Open decision (flagging, not blocking):** stage = calendar week (canon
2 missions/week) vs. release batch (whatever the instructor has released
together). Recommend **week** — stable, matches the novel's chapter
cadence; release gating stays an independent overlay (a locked mission
shows as a dimmed slot in its week).

---

## 3. Stage completion & quality — mechanics detail

- Stage completion: `submitted_missions / stage_missions` (released or
  not — unreleased shows as locked slots so the denominator is honest).
- Stage grade: min tier across the stage's *submitted* missions
  (min, not average — "a stage is as strong as its weakest evidence,"
  and it makes the resubmit incentive legible). ★=common ★★=epic
  ★★★=legendary.
- Campaign done = 6/6 stages at 100%. Campaign grade = the 6 stage
  grades shown as a row — deliberately NOT averaged into one number
  (averages hide the story; six stars tell it).
- `StageCompleted` event when a learner's stage hits 100% (celebration +
  feed + world-state hook later; also the natural place for the missing
  chapter-unlock celebration flagged in GAPS.md).

## 4. Minecraft quests: visible only after linking

Agreed, with one refinement: **hide the content, keep one teaser slot.**
The app's established lock language is "visible but silhouetted, never
hidden" — full hiding hurts discoverability of the coolest layer. So:
unlinked learners see a single card ("Basin telemetry offline — connect
your Minecraft account to reveal Field Ops"), not the quest list, not
quest columns on the Campaign Map, not the Field Ops Log on the Dossier.
After linking (§7), all Basin surfaces materialize.

## 5. Mini-kit collection: **the Aqueduct Kit**

LEGO-Star-Wars minikits, EVOKE-shaped: **10 components of a water
filter/aqueduct model**, one hidden on each major screen (Now, Map,
Story, Cohort, Training, Dossier, Vault, Debrief, Team, Field Kit).
Visible-but-must-visit (a small glowing component icon — distinct from
the Alchemy Signal's cryptic ⬡, which stays secret-tier), so the
mechanic literally *teaches the navigation* — it rewards visiting every
surface once, which is the nav-confusion fix working from the bottom up.

Collect all 10 → the assembled Aqueduct animates on the Dossier
(CSS-drawn, water flowing) + a real in-game reward via the existing
bridge (e.g. a named "Aqueduct Blueprint" item) + feed entry.
Implementation reuses the fragment pattern (`minikit:<piece>` rows in
`minigame_scores`, server-tracked, one-time XP).

## 6. Words of Wisdom: the daily B1llbot check-in as reflection collector

Upgrade the silent daily check-in (+10 XP, invisible) into the **Field
Report**: once per day, the learner tells B1llbot what they did or are
thinking (one message, drawer / full-screen / **Field Kit on their
phone** — this is the phone's killer daily loop). B1llbot answers with a
**Word of Wisdom**: an in-persona line grounded in his RAG lore,
timestamped and kept.

- New `daily_reflections` table (user, date, text, reply); one/day.
- **Wisdom Journal**: collected Words of Wisdom + your own reflections,
  on the Dossier and the Vault — over a semester this becomes the
  learner's own reflective journal, which is the real pedagogy.
- Check-in XP moves here (auto-checkin stays as silent fallback so
  nobody *loses* XP for skipping the chat).
- **Proposal needing sign-off:** ≥10 reflections unlocks the
  **Transformation** Power (one of the two Powers §4.1 left correctly
  dark pending §7.2/§7.3). Daily reflection ("learns from experience,
  adapts") is a defensible trigger, but it touches the skills framework —
  flagged as a decision, not built silently.

## 7. QR scan → registered phone (no login)

The Hub QR currently opens the companion, which dev-logins as Player One
— wrong the moment there are two learners. Fix: **pairing tokens.**

- QR encodes `companion.html?pair=<one-time-token>` where the token
  (new `pairing_tokens` table: user_id, token, 10-min expiry, single-use)
  was minted for the *logged-in web user* when the Hub rendered.
- Companion exchanges token → identity, stores it locally; the phone is
  now that learner, no login, works under LTI too (the web session came
  from the LTI launch).
- Safety: single-use + short expiry + a visible "Pairing as **{name}** —
  that's you?" confirm; a classroom projector showing someone's QR is the
  threat model, and the confirm + expiry covers it. Re-render regenerates.

## 8. Minecraft linking as a two-channel confirm (the "MFA" idea)

Yes — and Wave 2 accidentally built the hard part. The bridge already
reads scoreboards, and vanilla Minecraft has the `/trigger` command:
**player-executable, no mods, no permissions, works for Bedrock players
via Geyser.** So:

1. Phone/web: "Connect Minecraft" → shows a short numeric code
   (`4712`) bound to your account (10-min expiry).
2. In Minecraft, the player types `/trigger evoke_link set 4712`.
   (Bridge enables the trigger objective for online players each
   heartbeat tick.)
3. Bridge polls the trigger scoreboard (existing machinery), matches the
   code → creates the link **pending confirmation**, and tellraws the
   player in-game: "✔ Link requested for Agent {name} — confirm on your
   phone."
4. The phone (already live via WebSocket) pops the confirm: "Minecraft
   player **{username}** wants to link — Confirm / Deny."
5. Confirm → link finalized, celebration both places; Basin surfaces
   materialize (§4).

That's genuine two-channel possession proof (web session + in-game
presence), it replaces the demo-only "first player auto-links to Player
One" heuristic for real cohorts (keep the heuristic behind a dev flag),
and it solves Floodgate's prefixed-username problem for free — the code
identifies the account, not the username shape.

---

## Build order (each independently shippable, verified like Waves 1–2)

| # | Piece | Touches | Est. size |
|---|---|---|---|
| W3.1 | Campaign Map API + screen + compact strip; StageCompleted event | main.py, workers.py, screens.js, app.js, theme.css | M |
| W3.2 | Nav/IA restructure + Hub reorder (Next Action first, world strip compact) | app.js, screens.js, theme.css | S |
| W3.3 | Basin conditional display (teaser card until linked) | screens.js, companion | S |
| W3.4 | Aqueduct Kit (10 pieces, assembly on Dossier, in-game reward) | main.py, games.js, screens, bridge | M |
| W3.5 | Field Report / Words of Wisdom + Wisdom Journal | main.py (table+API), billbot surfaces, dossier/vault, companion | M |
| W3.6 | QR pairing tokens (phone auto-registration) | main.py, hub QR, companion | S |
| W3.7 | `/trigger` link codes + phone confirm (two-channel linking) | main.py, bridge, companion, screens | M |
| W3.8 | Docs: GAPS.md updates; UI_SPEC nav section rewrite | docs | S |

Dependencies: W3.6 before W3.7 (the confirm step needs a paired phone);
W3.1 before W3.2 (the Hub strip embeds the map); everything else
parallel.

**Decisions explicitly left open for Nathan / narrative / curriculum:**
1. Stage = week (recommended) vs. release batch (§2).
2. Reflections → Transformation Power trigger (§6) — skills-framework
   territory.
3. Whether the demo auto-link heuristic stays on by default in dev (§8).
