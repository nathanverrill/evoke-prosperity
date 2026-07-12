# EVOKE Prosperity — handoff to UX design

This covers the **entire application** — every screen that exists today, every screen that's designed but not yet built, and where the other two pieces of the product (the graphic novel and the Minecraft world) fit around the web app you're actually restyling.

---

## 1. For you (plain-language version)

**What this is:** EVOKE Prosperity is a financial-literacy program for teens told across three connected pieces:

1. **A graphic novel** — the story (Alex, a kid from the struggling town of Keel, climbing a mountain of increasing wealth/opportunity to bring something better back home).
2. **The web app ("Operations Hub")** — this is what you're designing. The learner's mission control.
3. **An optional Minecraft world ("Basin Simulation")** — a 3D version of the same story world learners can explore, with an in-game AI mentor character.

The feel we're going for everywhere: **"Urgent Evoke, not an LMS."** The learner is an EVOKE Agent at mission control, not a student on a homework portal — missions, evidence, insights, awards, never assignments/uploads/comments/grades.

**Your scope is #2, the web app** — but it's the hub that ties the other two together (it links out to Minecraft account-linking, it hosts the novel reader, it's where a teacher/instructor works), so this doc explains all three so you have the full picture.

**What exists today, fully working, just undesigned:** Every screen below is real — real data, real navigation. It's all rendered in our deliberate wireframe style: grayscale boxes, one flat accent color, system font, no shadows, no personality. That's on purpose — nothing here is "half-finished," it just hasn't been designed yet.

### Every screen a learner sees (built, wireframe-only)

| Screen | What it is |
|---|---|
| **Operations Hub** (home) | Landing page — current missions, class-wide activity feed, notifications, streak/check-in status |
| **Novel reader** | Graphic-novel panel viewer, one chapter per story week |
| **Mission brief** | A mission's story framing + evidence upload |
| **Mission debrief** | What happens after you submit — a live-updating timeline (Submitted → AI Analysis → Instructor Review → Complete), the award earned, insights/feedback |
| **Gallery** | Browse the whole class's completed work; open someone else's debrief to leave peer feedback |
| **Player Profile** | XP/level, the 4 Superpower badges, the 16-Power Achievements grid, missions/quests completed, award cabinet |
| **Team Profile** | Team roster, shared XP, member badges |
| **Companion Mode** | A narrow sidebar-style page for chatting with B1llbot (the AI mentor) outside a mission |
| **B1llbot drawer** | Present on *every* screen — a persistent chat widget, not a separate page |

### Screens that are designed in spec but don't exist as a page yet

These are real, flagged gaps (see `GAPS.md`) — worth designing even before engineering builds them, since design and build can happen in parallel here:

| Missing screen/flow | What it needs to do |
|---|---|
| **Onboarding / "Mission Zero"** | First-login flow — nothing exists today. A new learner just lands on the Hub cold. Needs a scripted first-run: story cold-open, account/Minecraft linking, team formation, first mission intro. |
| **Instructor Dashboard** | The backend already tracks this data, there's just no page: which students are stuck, who hasn't submitted, pending reviews, class-wide quest activity. (Note: this is different from the "teacher-review" grading screen you'll see in the sim — that one's a stand-in for the real Brightspace gradebook and isn't really yours to redesign. This dashboard is.) |
| **Non-Minecraft / "web-only agent" path** | Minecraft is optional, but right now everything (quest cards, link-account prompts, Companion Mode) quietly assumes a learner has it. Needs a genuine alternate experience for learners without Minecraft access — e.g. a real-world "field observation" quest form instead of an in-game one. |
| **Celebration moments** | Badge earned, level up, chapter unlock, campaign finale — all currently render as a plain toast notification. These are the emotional peaks of the whole product and deserve real full-screen moments, especially the Legendary award tier and the Week 6 campaign finale. |
| **Notification digest / "you have something waiting"** | The bell icon exists, but there's nothing for a learner who doesn't log in for a few days, or a teacher-facing "3 students have uncollected awards" nudge. |
| **Evidence submission scaffolding** | Right now it's a bare file upload + one optional text field. Each mission already has a defined Superpower/skill/domain it teaches — worth designing 1–2 guided reflection prompts per mission instead of a blank box. |

### Things worth designing intentionally, beyond just "make it pretty"
- **B1llbot's presence** — he's a character (a retired, folksy field-guide businessman — see `GAME_DESIGN.md` §3.3 for his full voice), not a generic chat-bot UI. He also exists as an in-game Minecraft NPC (see below) — his visual/tone identity should feel like the same character in both places, even though the actual implementation is completely different.
- **Award tiers** (Common / Epic / Legendary) — right now gray/blue/gold text chips. Legendary especially should feel like the biggest moment in the loop.
- **Locked content** — future missions, undiscovered chapters, locked Achievement tiles are all meant to be *visible but silhouetted*, never hidden — that convention should read consistently everywhere it shows up.
- **The world's own visual language** — the story moves through three tiers (Keel: scrappy/home, Halyard: corporate/costly, Oasis: advanced/pressured — see `GAME_DESIGN.md` §2). Worth letting that inform color/mood shifts as a learner progresses, not one flat theme for the whole app.
- **Accessibility** — reading level of narrative copy, a dyslexia-friendly type option, alt text for novel panels, keyboard navigation. A real procurement question for public schools, expensive to retrofit later.
- **Chromebook and phone** — the real classroom hardware is managed Chromebooks (1366×768) and phones, not designer monitors. 45-minute class periods also matter: the Hub should always be able to answer "what can I do in the next 10 minutes?"

### The other two surfaces (for context — not what you're restyling)
- **The graphic novel content itself.** The reader UI is in your scope (it's a web-app screen); the actual chapters/art are a separate, still-open production question (`GAPS.md`: "Graphic-novel content pipeline is undefined") — nobody's decided who illustrates it yet. Chapters currently load from a placeholder JSON manifest (`evoke/static/content/chapters.json`) with no real art.
- **The Minecraft Basin Simulation.** A real, separately-built 3D world (Java + Bedrock via Geyser/Floodgate) with its own B1llbot NPC, quest mechanics, and in-game economy. It's a completely different toolchain — Minecraft resource packs / mod GUIs, not CSS — almost certainly not something you're restyling directly. It's listed here so you know it exists and so B1llbot's character (and any shared iconography, like award tiers) can stay consistent across both surfaces if that ever comes up.

**A reference point, not a spec to copy exactly:** `ui/Final Prosperity Showcase.html` in the repo is an earlier polished mockup of the web app. Treat it as a reference for *flow and feature set*, not a pixel target — the actual screen set has evolved since it was made.

**Where your work actually goes:** every color, spacing value, and visual style in the whole web app lives in exactly two files: `tokens.css` and `theme.css`. You (or your Claude) never need to touch page layout logic or JavaScript — the app was deliberately built so a designer can restyle it just by replacing those two files.

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
3. Wait — it brings up several services (including a Minecraft server, which you can ignore) and seeds some demo data. Takes roughly 1–2 minutes. You'll see a checklist print out as things come online.
4. Open your browser to **http://localhost:8000** — that's the Operations Hub. You're automatically signed in as a demo learner, no login step needed.
5. Also worth opening:
   - **http://localhost:8000/companion.html** — Companion Mode (the standalone B1llbot chat page)
   - **http://localhost:8001/teacher-review** — the instructor grading stand-in (useful context, not something you're redesigning — see the Instructor Dashboard note above for the screen that *is* yours)
6. Click through: submit a mission's evidence (any file works), watch the debrief timeline update, check the Profile page, visit the Gallery.
7. When you're done for the day, shut it down from the repo folder:
   ```
   cd evoke-infra && docker compose down && cd ../evoke && docker compose down
   ```
   (Your data isn't lost — running `./quick-start.sh` again picks up where you left off, unless you also add `-v` to those `down` commands, which wipes it for a clean slate.)

---

## 3. For your Claude

### Read these first, in this order
1. **`UI_SPEC.md`** — the full screen spec (every existing screen listed above, in detail) and the **wireframe skinning contract**: *"Single static SPA... vanilla JS... The UX designer restyles by replacing `tokens.css` (and `theme.css`), never markup or JS."* That constraint is load-bearing for this whole handoff — restyle through the token/theme layer, don't refactor `screens.js`/`app.js`.
2. **`GAME_DESIGN.md`** — world, characters, tone, and B1llbot's voice (§3.3, §10), plus the three-tier world (§2: Keel/Halyard/Oasis). Read this before designing *any* copy-adjacent visual choice (icons, color moods per world-tier, award-tier language) — it's the source of truth for what everything is supposed to feel like. §4/§4.1 cover the Achievements grid specifically.
3. **`GAPS.md`** — the authoritative list of what's missing across the whole product, not just styling. The "User experience" and "Gamification" sections (search for "No onboarding," "No instructor UI," "second-class," "No celebration moments," "No choice or expression") are the source for the "not built yet" screens listed above — worth reading in full before proposing new flows, so design work doesn't quietly re-decide something already settled (or already flagged as an open decision) elsewhere in these docs.
4. **`ARCHITECTURE.md`**, skim only — explains why the product is structured as three separate surfaces (web/novel/Minecraft) sharing one event stream, useful context for why Minecraft isn't part of this restyle.

### Where the web app actually lives
- **Styling — this is what you'll edit:**
  - `evoke/static/tokens.css` — every color/spacing/radius/shadow value in the app. Currently deliberate wireframe values (grayscale + one flat accent, system font, 1px borders, no shadows/gradients). Meant to be replaced wholesale.
  - `evoke/static/theme.css` — component-level rules built from those tokens (cards, badges, timeline steps, awards, nav, the B1llbot drawer, etc.).
  - `evoke/static/layout.css` — grid/flex structure (columns, gaps, spacing) — edit here for layout changes that don't require touching markup.
- **Markup/logic** (reference only — don't edit unless the human explicitly asks): `evoke/static/screens.js` (one function per screen — `hub`, `novel`, `missionBrief`, `missionDebrief`, `gallery`, `playerProfile`, `teamProfile`), `evoke/static/app.js` (router, top bar, B1llbot drawer shell), `evoke/static/companion.html` (standalone page, own markup).
- No build pipeline anywhere in this app — plain CSS/JS, loaded directly via `<link>`/`<script>` tags. Whatever you write has to work as-is, no preprocessor.
- The screens listed as "not built yet" above have no corresponding file — if design work produces mockups for those, they're concept work to hand back to engineering, not something to implement directly against a route that doesn't exist.

### The Achievements grid, specifically
The newest and most detailed single component — 16 small "Power" tiles (e.g. Empathy, Courage, Teamwork, Curiosity) that light up individually and roll up into the 4 existing Superpower badges above them.
- Rendered inside `Evoke.screens.playerProfile` in `screens.js` (~line 370): the existing 4-tile `.badge-wall` for Superpowers, then a new `<h2>Achievements</h2>` section below it rendering the 16 Powers grouped by Quality, reusing the same `.badge-tile` component.
- Relevant classes in `theme.css`: `.badge-tile` (~line 113), `.badge-tile.is-earned`, `.badge-tile.is-dimmed`, `.badge-tile__name`, `.badge-tile__progress`. Grid layout in `layout.css`: `.badge-wall` (~line 84).
- Each earned tile carries a `title="..."` attribute with that Power's real definition (currently a native browser tooltip — a real tooltip/popover component would likely read better).
- Each tile also knows `tag_type`: `"primary"`, `"secondary"`, or `"behavioral"` — available if a different visual treatment per type is wanted.
- Full design rationale (why 16 Powers, why 2 of them unlock from behavior instead of missions, the World Bank framework they're drawn from): `GAME_DESIGN.md` §4 and §4.1.

### Constraints to keep in mind everywhere
- Must hold up at 1366×768 (managed Chromebooks) and at phone width — this is a real classroom deployment.
- Keep contrast readable — this is a K-12 product.
- Locked/gated content (future missions, chapters, Achievement tiles) should read as *visible but silhouetted*, never hidden entirely — that convention already exists in `UI_SPEC.md` for the graphic-novel chapter rail and should extend consistently to every other place something is locked.
