# UI_SPEC.md — EVOKE Prosperity web experience

Companion to [`BUILD_PLAN.md`](BUILD_PLAN.md). Defines the gamified web app this build ships: the screens, the mission loop, the two profile pages, Companion Mode, and the **wireframe skinning contract** the UX designer will restyle against. Narrative/tone source: `CONCEPTS.md` glossary and `docs/canon/`. Interaction reference: `ui/Final Prosperity Showcase.html` (the polished mockup — design target for flow and feature set, not for implementation).

**The feel to hit:** Urgent Evoke, not an LMS. The learner is an EVOKE Agent at mission control ("Operations Hub"), not a student on a homework portal. Missions, evidence, insights, awards — never assignments, uploads, comments, grades. Every learner action gets an immediate, visible response (a notification, XP tick, timeline step lighting up) so the event pipeline *feels* alive.

---

## Information architecture

```
/                        Operations Hub (home)
/welcome                 First-run onboarding (shown once per learner, never on a deep link)
/novel                   Graphic novel reader (current chapter)
/gallery                 Class-wide gallery of completed mission work; open one to leave peer feedback
/mission/{id}            Mission brief + evidence submission (locked/silhouetted if not yet released)
/mission/{id}/debrief    Mission completion / debrief (?fresh=1 -> full-screen celebration first)
/mission/{id}/vault      Revisit-anytime retrospective for a completed mission
/profile                 Player profile (own) -- Superpowers, the 16-Power Achievements grid, Quests, Award Cabinet
/profile/{user_id}       Player profile (public view)
/team/{team_id}          Team profile
/billbot                 Full-screen B1llbot chat (in addition to the persistent drawer on every screen)
/map                     Campaign Map -- the "what done means" infographic: instructor-configured stages,
                         completion rings, star quality grades, Basin quest markers (linked players only)
/arcade                  Field Ops / Training Sims (Flow Control, Signal Decrypt) + leaderboards
/game/flow, /game/decrypt  The two Training Sims themselves
/alchemy                 Hidden -- unlocks via the 5-fragment Alchemy Signal scavenger hunt
/faq                     Connect-to-Basin instructions, "what does done mean," Field Report explainer
/admin                   Instructor Ops Deck: cohort table, mission release + stage assignment -- not in the
                         learner nav, direct-URL only, no role check yet
/companion               The Field Kit (installable PWA) -- registered to a learner via the Hub QR's
                         one-time pairing token; daily Field Report, Basin linking, quests, B1llbot
```

**Learner nav (July 2026 IA):** the showcase's **left nav rail** pattern (`ui/Final Prosperity Showcase.html`'s `primary-nav`), ported verbatim — brand lockup on top, then big icon+label items (Material Symbols + Unbounded), cyan-highlighted when active; collapses to a fixed bottom tab bar under 900px. Items, ordered by the learner's questions: `Home (#/) · Campaign Map (#/map) · Story (#/novel) · Cohort (#/gallery) · Field Ops (#/arcade) · B1llbot (#/billbot) · Dossier (#/profile)`. B1llbot appears in the rail (as in the showcase) *and* remains the persistent drawer.

All of the above beyond the original six routes were added after this doc was first written — `GAPS.md` is the source of truth for what's shipped vs. still open; this list is kept in sync with it, not the other way around.

Single static SPA served by FastAPI `StaticFiles` (no build pipeline, per `ARCHITECTURE.md`) — hash-or-history routing in vanilla JS is fine. Persistent elements on every screen: top bar (agent name, XP/level meter, streak, notification bell) and B1llbot chat drawer.

## The mission loop (core gameplay)

Mirrors the four-beat loop in the showcase mockup:

**1. Graphic novel (`/novel`)** — the story beat that frames the week's missions. Full-bleed panel pager (image + caption panels, keyboard/click advance). Chapter unlocks are driven by mission progress (`MissionCompleted` events); locked chapters show as silhouetted/disabled in a chapter rail. Last panel of a chapter ends on a call-to-action button: "Open Mission Brief →".

**2. Mission brief (`/mission/{id}`)** — the mission as story assignment. Shows: arc + week chip, title, narrative brief (markdown from the mission record, which — per `BUILD_PLAN.md` — came from the Brightspace sim), the Superpower it builds toward, PFL domain, evidence requirements, and the paired Minecraft quest card (clearly marked *optional — Basin Simulation*). Primary action: evidence upload → `POST /api/submit-evidence`. **Spec-vs-code note:** this line used to describe a "file + optional reflection text" form; the shipped form (`screens.js`) is a bare file input with no reflection field at all — see `GAPS.md`'s "Evidence submission has no scaffolding" gap. Treat the reflection text as aspirational until it's actually built, not as something already there. On submit, the **timeline strip** for this mission animates live: Submitted → Processing → AI Analysis → Instructor Review → Complete (polls the existing `learner-timeline` projection; each step lights as its event lands). The common-tier award notification should visibly arrive within seconds of submitting — that immediacy is the hook.

**3. Mission debrief (`/mission/{id}/debrief`)** — completion payoff. Insights (AI + instructor feedback, additive, never overwritten), awards earned for this mission with **Collect** buttons (uncollected awards pulse), XP gained, badge progress delta, and the next-story hook ("Chapter 3 unlocked"). Collect calls `POST /api/awards/{award_id}/collect` — same endpoint as Companion Mode; copy should hint the reward lands in Minecraft ("Delivered to your agent in the Basin").

**4. Operations Hub (`/`)** — mission control between missions. Zones:
- **Now**: current mission card (or "read the next chapter" if story-gated), streak, pending-award count.
- **Mission board**: all 12 missions as cards in 4 arc columns (Explore / Imagine / Act / Communicate), states: locked / available / submitted / in-review / complete. This is the map of the whole campaign.
- **Feed**: reverse-chron event feed rendered from the learner's timeline projection (awards, insights, quest completions, team activity) — the visible heartbeat of the Redpanda stream.
- **Rails**: mini player card (XP/level/badges → links to `/profile`), mini team card (→ `/team/{id}`), B1llbot prompt.

## Profile pages

Both render **entirely from the OpenSearch profile projections** (`GET /api/profile/player/{user_id}`, `GET /api/profile/team/{team_id}`) — no request-time aggregation. Both must handle empty/zero states gracefully (new agent, new team).

**Player profile (`/profile`)**
- Header: agent name, level + XP bar (XP is additive-only), streak, linked Minecraft username (or link-account form — existing `/api/minecraft/link`).
- **Badges**: the four Superpowers (Empathetic Changemaker, Systems Thinker, Creative Visionary, Deep Collaborator) as a 2×2 wall — earned (lit, with date) vs in-progress (dimmed, with progress toward it).
- **Missions completed**: n/12 with a per-arc breakdown bar; list of completed missions with tier of best award earned.
- **Quests completed**: count + list of self-reported Minecraft quests, each showing its observation text and screenshot thumbnail (the player's personal field log — this is the only place side-quest "evidence" surfaces).
- **Award cabinet**: all awards by tier (common/epic/legendary), collected vs pending state.

**Team profile (`/team/{team_id}`)**
- Header: team name, member roster with `role_label` chips, aggregate level/XP.
- **Team mission progress**: which missions are done team-wide; team-scoped submissions (`TeamEvidenceSubmitted`) called out.
- **Combined badge wall**: per-member badge grid — reads as "our team's superpowers."
- **Quest log**: aggregate quest count + recent member quest completions (name + quest + when).
- Placeholder section for **Venture Points / Venture Spectrum** (weeks 4–6 missions) — render the section header and an "unlocks in the Act arc" state now so the layout is planned, wire later.

## Quest self-reporting

Available from the mission brief's quest card, the profile quest log, and Companion Mode: a "Report quest complete" flow — pick quest → optional observation text → optional screenshot upload → submit → `POST /api/mc-quests/{quest_id}/submit` → `QuestCompleted` event → toast + profile update. Copy must reinforce the canon rule: self-reported, for your own field log, never graded, never required.

## Companion Mode (`/companion`)

Keep the existing page's function (current mission, pending awards with Collect, B1llbot chat) and add the quest self-report shortcut. Restyle with the same wireframe tokens below. It stays a separate narrow page, not a responsive variant.

## Notifications

Bell in the top bar, count from `GET /api/notifications/{user_id}`. Every `AwardGranted` produces one. Clicking an award notification deep-links to the mission debrief with the award highlighted. Toasts for events that land while the page is open (poll the projection; SSE/websocket is a later upgrade, don't build it now).

---

## Wireframe skinning contract

The whole app ships deliberately unskinned — structure, layout, and interaction complete; visual identity absent. The UX designer restyles by **replacing one token file, never touching markup or JS.**

- **`static/tokens.css`** — every color, font, radius, shadow, and spacing step is a CSS custom property defined here and *only* here (`--color-bg`, `--color-surface`, `--color-accent`, `--tier-common/epic/legendary`, `--arc-explore/imagine/act/communicate`, `--font-display`, `--space-1..6`, `--radius`, …). Component CSS may only reference tokens, never literals. Wireframe values: grayscale + one flat accent, system font stack, 1px borders, no shadows/gradients — it should *look* like a wireframe so nobody mistakes it for the shipped design.
- **Semantic, stable class names** (`.mission-card`, `.badge-wall`, `.timeline-step.is-complete`, `.award.is-pending`) — these are the designer's API; renaming them later is a breaking change. State via `is-*`/`data-state` modifiers, not style mutation from JS.
- **Structural CSS separate from thematic CSS** (`layout.css` vs `theme.css`): grid/flex/positioning in layout, token-consuming looks in theme. The skin pass rewrites `theme.css` + `tokens.css` only.
- **Image slots, not baked images**: graphic-novel panels, badge art, and chapter art load from `static/content/…` paths with wireframe placeholders (labeled gray boxes) — art drops in by replacing files.
- No CSS framework, no build step. One deliverable to hand the designer: this section plus a screenshot set of every screen in wireframe state.

## Screen → API map (all existing or specified in `BUILD_PLAN.md`)

| Screen | Reads | Writes |
|---|---|---|
| Operations Hub | `/api/missions`, learner timeline projection, `/api/notifications/{user_id}`, `/api/profile/player/{id}` (mini card) | — |
| Novel | `/api/missions` (chapter gating) + static chapter content | — |
| Mission brief | `/api/missions`, `/api/mc-quests`, timeline projection | `/api/submit-evidence` |
| Debrief | timeline projection (insights), `/api/awards/{user_id}` | `/api/awards/{award_id}/collect` |
| Player profile | `/api/profile/player/{user_id}` | `/api/minecraft/link`, `/api/mc-quests/{quest_id}/submit` |
| Team profile | `/api/profile/team/{team_id}` | — |
| Companion | same as today + quest submit | collect, quest submit, `/api/billbot/chat` |
| B1llbot drawer | — | `/api/billbot/chat` |
| Campaign Map | `/api/progress-map/{user_id}`, `/api/world-state` | — |
| Field Ops / Training | `/api/minigames/{key}/leaderboard`, `/api/minigames/signal/{user_id}` | `/api/minigames/{key}/score`, `/api/minigames/signal/fragment` |
| Dossier extras | `/api/gear/{user_id}`, `/api/minigames/kit/{user_id}`, `/api/reflections/{user_id}`, `/api/achievements/{user_id}` | `/api/gear/{user_id}/equip`, `/api/avatar/{user_id}`, `/api/profile/{user_id}/sigil` |
| Now (Field Report card) | `/api/reflections/{user_id}` | `/api/reflection` |
| Field Kit (pairing/linking) | `/api/minecraft/link-request/{user_id}`, `/api/minecraft/connect-info` | `/api/companion/pair`, `/api/minecraft/link-code`, `/api/minecraft/link-confirm` |
| Instructor Ops Deck | `/api/admin/cohort`, `/api/admin/missions` | `/api/admin/missions/{id}/release`, `/api/admin/missions/{id}/stage` |
| Live layer (all screens) | `WS /ws` — pushed events (ActivityPosted, WorldStateAdvanced, LevelUpped, MinecraftPresence, MinecraftLinkRequested…) | — |

## Explicitly out of scope

- Visual design, art, animation polish (designer's pass).
- Instructor-facing UI (teacher flow stays in the Brightspace sim's review screen, by design).
- Real-time push (SSE/websockets) — polling the projections is fine at pilot scale.
- Accessibility audit beyond semantic HTML + keyboard operability of the novel reader and forms (do those now; the audit comes with the skin).
