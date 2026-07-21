# Field Tablet handoff (2026-07-21)

Scope: the full rewrite of the phone-scanned QR page from "EVOKE Field Kit"
(a companion app) to **Billbot's Field Tablet** (an in-universe artifact),
plus wiring its evidence submission into the real grading pipeline. Written
so a fresh context (model or human) can pick this up without re-deriving it
from commit history. Covers commits `47c3927` through `3b65e68`.

## Scope: companion.html only, on purpose

There are **two** implementations of "the phone/companion experience" in
this codebase, and only one was touched:

1. **`evoke/static/companion.html`** — the real, standalone page. Both the
   QR code (`_companion_url`, `main.py`) and the desktop Ops Hub's "Or open
   it on your computer" link point here. **This is what got rewritten.**
2. **`index.html`'s embedded `#companion` screen** (`controller.js`,
   reached via the desktop "Open Field Kit" button) — a separate, parallel
   implementation last touched a few commits earlier (`47c3927`,
   `f4262bf`). **Deliberately left alone** — it still says "Notebook" and
   "Simulation," not "Mission Evidence" and "Field Training Simulator."
   This was an explicit scope decision (see the conversation this session
   came from), not an oversight. If parity between the two ever matters,
   that's a separate, not-yet-scoped pass.

## The narrative reframe

Not a companion app — an in-universe artifact. Billbot ejects this tablet
from his own chest and hands it to the player; everything on it reads as
something the player is physically holding. Concretely: page title,
`<h1>`, intro copy, and `manifest.webmanifest`'s PWA name (`"Billbot's
Field Tablet"` / short name `"Field Tablet"`) all changed; "Field Kit"
language is gone from this file (the embedded desktop screen still uses
it, see above).

Three tabs, unchanged count, renamed/rebuilt:

| Old | New | What changed |
|---|---|---|
| B1llBot | B1llBot | Added a pre-seeded greeting + 3 randomly-rotated suggestion chips (pool of 6) — this tab previously opened to a blank log with no chips at all on the phone (desktop always had them; phone never did) |
| Notebook → Mission Notes | **Mission Evidence** | Full rebuild, see below |
| Simulation | **Field Training Simulator** | Narrative rewrite only (Alpha Dynamics / construction-robot framing for why Minecraft); same 4 steps, same backend, same addresses |

The Rule of Law conduct gate was **not** touched in this pass — still the
original 5-point safety list, out of scope for this rewrite.

## Mission Evidence: what it actually is

Per explicit correction mid-session: there is no team-shared-evidence
concept here. Each mission is an individually-graded Brightspace
assignment. A student investigates in the real world, then files **exactly
one** submission: one photo + one observation/reflection. Not a journal,
not a running notebook — language like "Reflection"/"Journal"/"Notebook"
was deliberately scrubbed from this tab's copy.

**Daily Field Report** (the AI-wisdom reflection-journal feature) was
**removed from the phone** as part of this — explicitly superseded by
Mission Evidence, not merged into it. It's still fully intact on desktop's
embedded `#companion` screen (untouched, see scope note above) and its
backend (`workers.py`'s Field Report Worker, `daily_reflections` table,
`/api/reflection`, `/api/reflections/{user_id}`) is completely unaffected.

### It submits through the real pipeline — not a parallel system

This was the most significant engineering decision this session, made
after two rounds of correction: the first draft built an isolated
`mission_field_reports`-only flow that deliberately couldn't trigger
completion/grading (safe, but also pointless — it wasn't real evidence).
The final version does the opposite: **same pipeline as the desktop
Operations Hub, literally the same code**, so mobile and website can never
drift apart.

- **`_submit_evidence_core` / `_submit_reflection_core`** (`main.py`) —
  extracted from `/api/submit-evidence` / `/api/submit-reflection` with
  their existing logic unchanged. Both the original HTTP routes *and* the
  new `/api/mission-field-report` endpoint call these directly. Same DB
  writes, same S3 put, same `TeamEvidenceSubmitted` Kafka event, same
  Brightspace Submission Worker, same AI Coach Worker, same completion
  gate (`_complete_mission_for_user`).
- **New `kind='individual_evidence'`**, additive only — `team_product` and
  `individual_task` are byte-for-byte unchanged. This was necessary, not
  optional: `team_product`'s resubmission-guard and
  `_complete_mission_for_user`'s evidence check are both scoped to
  `(team_id, mission_id)`, meaning *any* teammate's submission satisfies
  the gate for *everyone* on the team. Reusing `team_product` as-is for a
  genuinely individual assignment would have let one student's Field
  Tablet submission silently complete a teammate's mission who submitted
  nothing themselves. `individual_evidence` checks/guards per
  `(user_id, mission_id)` instead — see the updated evidence-check query
  in `_complete_mission_for_user`, which now accepts either kind.
- **`team_id` is still attached to the row** (required — `_get_user_team`
  is a hard 400 if absent, since Brightspace Groups sync is how every
  student gets a team at all). This is infrastructure plumbing, not a
  "team assignment" concept — don't read a `team_id` column value on an
  `individual_evidence` row as meaning the work was collaborative.
- **`_build_field_report_pdf`** (new deps: `reportlab`, `Pillow`) — the
  captured photo + observation become a one-page PDF (EXIF-orientation
  corrected, since phone camera JPEGs carry rotation as metadata, not
  pixels). Required because the AI Coach Worker's `PdfReader(...)` step
  and the existing PDF-only validation on evidence uploads both expect a
  real PDF — same requirement `team_product` uploads already had.
- **`mission_field_reports`** (the table) still exists, but is now just a
  **display cache**: it stores the *original* photo (not the generated
  PDF) plus the observation, purely so the tablet's "View Submission" can
  show back what was actually captured, separate from the real
  `submissions` row that holds the PDF Brightspace/AI actually see.
- **Are-you-sure confirmation screen** — added between the filled form and
  the actual submit, since this now has real, permanent academic
  consequences ("This will be graded and can't be changed after you
  submit — same as submitting on Brightspace").

### Verified live, end-to-end, against a real team member with a real current mission

Photo → PDF generation → real `submissions` row (`kind='individual_evidence'`) →
real `mission_reflections` row → real `awards` row (`tier='common',
source='submission'`) → real epic-tier AI review (`tier='epic',
source='ai_review'`, confirming the generated PDF is genuinely readable by
`PdfReader`) → app correctly auto-advancing to the next current mission.
Also **live-confirmed a real, pre-existing Brightspace gap** while testing
(see `BRIGHTSPACE.md`'s 2026-07-21 entry) — a mapped, existing assignment
that isn't actually published/visible to the submitting student in
Brightspace itself, reproduced identically via the unmodified
`team_product` path on the same mission, so: not caused by this work, but
found because of it.

## Real bugs hit and fixed along the way (useful debugging precedent)

1. **CSS specificity: `.btn[hidden]` didn't hide anything.** `.btn`'s own
   `display:inline-flex` (both in `index.html`'s inline styles and
   `showcase.css`) beats the `hidden` attribute's UA-stylesheet
   `display:none` at equal specificity, last-rule-wins. Any `.btn` element
   toggled via `.hidden = true/false` in JS silently stayed visible. Fixed
   with an explicit `.btn[hidden]{display:none;}` rule in both stylesheets
   — this codebase's existing convention for the same problem
   (`.comp-pane[hidden]`, `.pf-picker[hidden]` already existed; `.btn`
   just never had one). If a future hide/show toggle on a `.btn` "doesn't
   work," check this first.
2. **JS temporal dead zone: `const` declared after code that can run
   synchronously before it.** `companion.html`'s conduct gate can call
   `enterField()` → `init()` synchronously, inline, during the script's
   first pass (already-accepted gate, common on a returning device) —
   *before* the script has reached a `const` declared further down the
   file. A fully synchronous function referencing that `const` (no
   `await` before the reference) throws `ReferenceError: Cannot access
   'X' before initialization`; an `async` function whose first real work
   is an `await` does *not* have this problem, because the `await` yields
   and lets the rest of the script run to completion first. Fix: put
   anything referenced by a function reachable from the gate's synchronous
   path *before* the gate-check code in the file, not after. Bit twice in
   this session (`BILLBOT_GREETING`/`BILLBOT_SUGGESTIONS`, then avoided
   the second time by structuring `loadCurrentMission` as `async` with an
   early `await`).
3. **Brightspace assignment visibility ≠ existence.** Covered fully in
   `BRIGHTSPACE.md`. Short version: a service-account token can see a
   Dropbox Folder that a specific student's own token can't — check both
   before assuming a submission failure is a code bug.

## Open / not done

- Desktop's embedded `#companion` screen is now visibly out of sync with
  the phone (old "Notebook"/"Simulation" copy, no Mission Evidence flow).
  Not a bug — an explicit scope decision — but worth knowing before anyone
  is surprised by the difference.
- No retry/backfill if a Brightspace sync fails (same "log and drop"
  behavior `BRIGHTSPACE.md` already documents for the desktop path —
  `individual_evidence` inherits it unchanged, nothing new here).
- No edit/resubmit path for a filed Mission Evidence report — deliberate
  ("No editing required for now" in the original spec), but if that
  changes, note that `_submit_evidence_core`'s resubmission-guard for
  `individual_evidence` already supports it mechanically (same
  `ON CONFLICT`-free upsert pattern as `team_product`'s resubmit path) —
  it would just need a UI to reach it.
