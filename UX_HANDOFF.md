# EVOKE Prosperity — handoff to UX design

This covers the **whole web app**, not just one feature. Everything below the wireframe level is intentionally undesigned right now — this is the handoff to make it real.

---

## 1. For you (plain-language version)

**What this is:** EVOKE Prosperity is a financial-literacy program for teens told across three connected pieces: a graphic novel, a web app ("Operations Hub"), and an optional Minecraft world. The web app is what you're designing. The feel we're going for everywhere: **"Urgent Evoke, not an LMS."** The learner is an EVOKE Agent at mission control, not a student on a homework portal — missions, evidence, insights, awards, never assignments/uploads/comments/grades.

**What exists today:** Every screen below is fully built and working — real data, real navigation, nothing fake. But it's all in our deliberate wireframe style: grayscale boxes, one flat accent color, system font, no shadows, no personality. That's on purpose — it means nothing is "half-finished," it just hasn't been designed yet. Your job is to make it feel like the game it's supposed to be, not to fix anything broken.

**The screens that need your eyes** (this is the whole app — every page a learner sees):

| Screen | What it is |
|---|---|
| **Operations Hub** (home) | The landing page — current missions, a class-wide activity feed, notifications, streak/check-in status |
| **Novel reader** | Graphic-novel panel viewer, one chapter per story week |
| **Mission brief** | A mission's story framing + evidence upload |
| **Mission debrief** | What happens after you submit — a live-updating timeline (Submitted → AI Analysis → Instructor Review → Complete), the award you earned, insights/feedback |
| **Gallery** | Browse the whole class's completed work; open someone else's debrief to leave them peer feedback |
| **Player Profile** | XP/level, the 4 Superpower badges, the 16-Power Achievements grid underneath them, missions/quests completed, award cabinet |
| **Team Profile** | Team roster, shared XP, member badges |
| **Companion Mode** | A narrow sidebar-style page for chatting with B1llbot (the AI mentor) outside of a mission |
| **B1llbot drawer** | Present on *every* screen — a persistent chat widget, not a separate page |

**Things worth designing intentionally, beyond just "make it pretty":**
- **B1llbot's presence** — he's a character (a retired, folksy field-guide businessman — see `GAME_DESIGN.md` §3.3 for his full voice), not a generic chat-bot UI.
- **Award tiers** (Common / Epic / Legendary) — right now they're just gray/blue/gold text chips. The Legendary tier especially should feel like the biggest moment in the loop.
- **Locked content** — future missions, undiscovered chapters, and locked Achievement tiles are all meant to be *visible but silhouetted*, never hidden — the same "locked = seen, not secret" treatment should read consistently everywhere it appears.
- **The world's own visual language** — the story moves through three tiers (Keel: scrappy/home, Halyard: corporate/costly, Oasis: advanced/pressured — see `GAME_DESIGN.md` §2) — worth letting that inform color/mood shifts as a learner progresses, not just a single flat theme for the whole app.
- **The Achievements grid specifically** — a newer, more detailed piece (16 small "Power" tiles that build up to the 4 Superpower badges). Worth extra attention since it's the newest and most complex single component. Full detail on it is in §3 below and in `GAME_DESIGN.md` §4.1.
- **Chromebook and phone** — the real classroom hardware is managed Chromebooks (1366×768) and phones, not designer monitors.

**A reference point, not a spec to copy exactly:** `ui/Final Prosperity Showcase.html` in the repo is an earlier polished mockup. Treat it as a reference for *flow and feature set*, not a pixel target — the actual screen set has evolved since it was made.

**Where your work actually goes:** every color, spacing value, and visual style in the whole app lives in exactly two files: `tokens.css` and `theme.css`. You (or your Claude) never need to touch page layout logic or JavaScript — the app was deliberately built so a designer can restyle it just by replacing those two files.

---

## 2. How to run the app yourself

You don't need to know how any of this works — just follow these steps. If anything errors, paste the error to your Claude and it'll sort it out.

**Before you start:** install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and make sure it's running (you'll see its icon in your menu bar/taskbar).

1. Get the code onto your machine (skip if you already have the repo folder):
   ```
   git clone <the repo URL your team gives you>
   cd evoke-prosperity
   ```
2. Run the start script:
   ```
   ./quick-start.sh
   ```
3. Wait — it brings up several services and seeds some demo data. Takes roughly 1–2 minutes. You'll see a checklist print out as things come online.
4. Open your browser to **http://localhost:8000** — that's the Operations Hub. You're automatically signed in as a demo learner, no login step needed.
5. Also worth opening:
   - **http://localhost:8000/companion.html** — Companion Mode (the standalone B1llbot chat page)
   - **http://localhost:8001/teacher-review** — the instructor grading view (useful context, not something you're redesigning, but shows how a submission's story ends)
6. Click through: submit a mission's evidence (any file works), watch the debrief timeline update, check the Profile page, visit the Gallery.
7. When you're done for the day, shut it down from the repo folder:
   ```
   cd evoke-infra && docker compose down && cd ../evoke && docker compose down
   ```
   (Your data isn't lost — running `./quick-start.sh` again picks up where you left off, unless you also add `-v` to those `down` commands, which wipes it for a clean slate.)

---

## 3. For your Claude

### Read these first, in this order
1. **`UI_SPEC.md`** — the full screen spec (every screen listed above, in detail) and the **wireframe skinning contract**: *"Single static SPA... vanilla JS... The UX designer restyles by replacing `tokens.css` (and `theme.css`), never markup or JS."* That constraint is load-bearing for this whole handoff — restyle through the token/theme layer, don't refactor `screens.js`/`app.js`.
2. **`GAME_DESIGN.md`** — world, characters, tone, and B1llbot's voice (§3.3, §10). Read this before designing *any* copy-adjacent visual choice (icons, color moods per world-tier, award-tier language) — it's the source of truth for what everything is supposed to feel like. §4/§4.1 specifically cover the Achievements grid if that's the first thing tackled.
3. **`GAPS.md`** — known UX gaps not yet resolved (search the "User experience" and "Gamification" sections) — e.g. "No celebration moments," "No onboarding," "No choice or expression." Worth knowing what's explicitly still open versus already decided, so design work doesn't quietly re-litigate something already settled elsewhere in these docs.

### Where the app actually lives
- **Styling — this is what you'll edit:**
  - `evoke/static/tokens.css` — every color/spacing/radius/shadow value in the app. Currently deliberate wireframe values (grayscale + one flat accent, system font, 1px borders, no shadows/gradients). Meant to be replaced wholesale.
  - `evoke/static/theme.css` — component-level rules built from those tokens (cards, badges, timeline steps, awards, nav, the B1llbot drawer, etc.).
  - `evoke/static/layout.css` — grid/flex structure (columns, gaps, spacing) — edit here for layout changes that don't require touching markup.
- **Markup/logic** (reference only — don't edit unless the human explicitly asks): `evoke/static/screens.js` (one function per screen — `hub`, `novel`, `missionBrief`, `missionDebrief`, `gallery`, `playerProfile`, `teamProfile`), `evoke/static/app.js` (router, top bar, B1llbot drawer shell), `evoke/static/companion.html` (standalone page, own markup).
- No build pipeline anywhere in this app — plain CSS/JS, loaded directly via `<link>`/`<script>` tags. Whatever you write has to work as-is, no preprocessor.

### The Achievements grid, specifically
The newest and most detailed piece — 16 small "Power" tiles (e.g. Empathy, Courage, Teamwork, Curiosity) that light up individually and roll up into the 4 existing Superpower badges above them.
- Rendered inside `Evoke.screens.playerProfile` in `screens.js` (~line 370): the existing 4-tile `.badge-wall` for Superpowers, then a new `<h2>Achievements</h2>` section below it rendering the 16 Powers grouped by Quality, reusing the same `.badge-tile` component.
- Relevant classes in `theme.css`: `.badge-tile` (~line 113), `.badge-tile.is-earned`, `.badge-tile.is-dimmed`, `.badge-tile__name`, `.badge-tile__progress`. Grid layout in `layout.css`: `.badge-wall` (~line 84).
- Each earned tile carries a `title="..."` attribute with that Power's real definition (currently a native browser tooltip — a real tooltip/popover component would likely read better).
- Each tile also knows `tag_type`: `"primary"`, `"secondary"`, or `"behavioral"` — available if a different visual treatment per type is wanted.
- Full design rationale (why 16 Powers, why 2 of them unlock from behavior instead of missions, the World Bank framework they're drawn from): `GAME_DESIGN.md` §4 and §4.1.

### Constraints to keep in mind everywhere
- Must hold up at 1366×768 (managed Chromebooks) and at phone width — this is a real classroom deployment.
- Keep contrast readable — this is a K-12 product.
- Locked/gated content (future missions, chapters, Achievement tiles) should read as *visible but silhouetted*, never hidden entirely — that convention already exists in `UI_SPEC.md` for the graphic-novel chapter rail and should extend consistently to every other place something is locked.
