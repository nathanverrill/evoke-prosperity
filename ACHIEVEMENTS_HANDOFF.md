# Achievements — handoff to UX design

A new feature just shipped on the backend: a 16-tile "Achievements" grid on the player Profile page, grouped under the 4 existing Superpower badges. It works, it's tested, and right now it looks like a wireframe (gray boxes, no icons, no personality). This doc is for handing it to design.

---

## 1. For you (plain-language version)

**What this is:** Each learner has 4 "Superpower" badges (Creative Visionary, Deep Collaborator, Systems Thinker, Empathetic Changemaker). We just added a layer underneath those: 16 smaller "Powers" (like Empathy, Courage, Teamwork, Curiosity) that light up one at a time as a learner does mission work. Once all 4 Powers under a Superpower are lit, that Superpower badge itself lights up. Think of it like 16 small achievements that build toward 4 big ones.

**What exists today:** The mechanic is fully working — data flows correctly, tiles light up at the right time, everything's tested. But the visual design is our placeholder wireframe style: plain boxes, light-green when earned, gray when locked, plain text. See the screenshot attached.

**What we need from you:** A real visual design for this grid — something that feels like a game achievement system, not a spreadsheet. Some things worth thinking about:
- Each of the 16 Powers could use its own small icon (they're abstract concepts — Empathy, Vision, Courage, Networking, etc. — so icons will need to be somewhat symbolic, not literal)
- What should it feel like the *moment* a Power unlocks? Right now it's silent — no animation, no celebration.
- How do the 16 small tiles relate visually to the 4 big Superpower badges above them? Right now they're just two separate grids stacked on the page.
- Locked tiles: right now they just say "locked" — is there a more inviting way to hint at what's still ahead without giving it away?
- This needs to work on a Chromebook and on a phone (that's the real classroom hardware) — nothing fancy that only works on a big screen.

**How to see it yourself:** The fastest way is to ask your Claude to spin up the project locally (instructions for it are below) and click around — screenshots don't do it justice since the "lighting up" happens live. If that's not practical, I'll send you a walkthrough screenshot separately.

**Where your work goes:** By design, all visual styling in this app lives in exactly two files (`tokens.css` and `theme.css`) — you never need to touch the markup or the JavaScript. Your Claude can make the visual changes directly in those files without needing to understand or risk breaking any of the underlying logic.

---

## 2. For your Claude

### Orientation — read these first, in this order
1. `UI_SPEC.md` — the whole app's screen spec and its **wireframe skinning contract**: "Single static SPA... vanilla JS... The UX designer restyles by replacing `tokens.css` (and `theme.css`), never markup or JS." That constraint is load-bearing — don't refactor `screens.js` or `app.js`, restyle through the token/theme layer only.
2. `GAME_DESIGN.md` §4 and §4.1 — the actual design rationale for this feature: the World Bank EVOKE "Social Innovators' Framework" (Freeman & Hawkins, 2016) that the 4 Qualities / 16 Powers come from, verbatim definitions for all 16, and why 2 of the 16 (Generosity of Spirit, Curiosity) unlock from *behavior* (peer comments, chatting with the mentor bot) rather than mission completion.
3. `GAPS.md`, Gamification section — search for "Achievements (16 Powers)" and "Badge criteria" for the one-paragraph shipped-status summary, and the adjacent rows ("No celebration moments", "No choice or expression") for related open gaps worth designing alongside this if there's appetite.

### Where the actual UI lives (don't touch structure, only style)
- **Markup/logic** (reference only — do not edit unless the human explicitly asks): `evoke/static/screens.js`, function `Evoke.screens.playerProfile` (~line 370). Renders two grids: the existing 4-tile `.badge-wall` for Superpowers, and a new section below it (`<h2>Achievements</h2>`) that renders the 16 Powers grouped by Quality, each reusing the same `.badge-tile` component.
- **Styling — this is what you'll actually edit:**
  - `evoke/static/tokens.css` — every color/spacing/radius value in the whole app lives here and only here. Currently deliberate wireframe values (grayscale, one flat accent, no shadows) — this file is meant to be replaced.
  - `evoke/static/theme.css` — component-level rules built from those tokens. The relevant classes: `.badge-tile` (line ~113), `.badge-tile.is-earned` (line ~120, currently just a border/background swap), `.badge-tile.is-dimmed` (line ~121), `.badge-tile__name`, `.badge-tile__progress`.
  - `evoke/static/layout.css` — `.badge-wall` (line ~84) controls the grid layout itself (columns/gaps).
- Every earned tile carries a `title="..."` attribute with that Power's real definition (shows as a native tooltip today — feel free to design a real tooltip/popover instead if that reads better).
- Each Power tile also knows `tag_type`: `"primary"`, `"secondary"`, or `"behavioral"` — currently just appended as text ("earned · primary"). This is available if a different visual treatment per type is wanted (e.g. primary = fuller glow than secondary).

### Running it locally to see the real thing
```
./quick-start.sh
```
Starts the full stack (Postgres/Redpanda/OpenSearch/MinIO/web) and seeds a demo learner. Then:
1. Open `http://localhost:8000`
2. Complete a mission or two from the Operations Hub to see tiles unlock live (or ask the human for a shortcut to jump straight to a profile with several Powers already earned — there's a seeded demo account).
3. Visit `#/profile` to see the current wireframe rendering of both grids.

### Constraints to keep in mind
- No build pipeline — plain CSS, no preprocessor, no framework. Whatever you write has to work as a `<link>`-loaded stylesheet as-is.
- Must hold up at 1366×768 (managed Chromebooks) and on phone-width screens — this is a real classroom deployment, not a marketing site.
- Keep dark-on-light contrast readable; this is a K-12 product.
- The 16 Powers are abstract nouns (Ideation, Aggregation, Transformation...) — resist the urge to invent literal icons that oversell a concept the copy doesn't actually claim.
