# Brightspace Setup

A practical setup guide: what a human has to do by hand in Brightspace and
`/admin` today, and what's already automatic. See `BRIGHTSPACE.md` for the
deeper architecture writeup and live-verification history this doc
summarizes into action items.

## What actually talks to what (accurate as of 2026-07-21)

Everything that actually runs today goes through **OAuth** — either the
admin's cached **service-connection token** (reads: pulling assignments,
classlist, grade values) or a **student's own token**, minted fresh at
every real login (submitting evidence, syncing grades). Both live in
`evoke/oauth_providers.py`.

**`evoke/lms/brightspace_lms.py`** (the older `BRIGHTSPACE_APP_KEY`/
`BRIGHTSPACE_APP_SECRET` service-account adapter) and the old
`sync_missions_from_lms` auto-sync against `brightspace-sim` are **dead
code** — nothing in `main.py` or `workers.py` imports or calls either one.
`BRIGHTSPACE.md` (written 2026-07-19) still lists `BRIGHTSPACE_APP_KEY`/
`SECRET` as an open setup item for "the real submission/grading
round-trip" — that's now stale. **Don't set those up expecting them to be
required; nothing live reads them.** If a future rebuild actually wants a
service-account path (e.g. for actions no student token could ever cover),
treat it as new work, not finishing a partially-done thing.

---

## Part 1 — One-time manual setup

Needs a human with instructor/course-admin rights in Brightspace, done
once per course offering:

1. **OAuth app registration** — Brightspace's Manage Extensibility admin
   tool. Gives `BRIGHTSPACE_CLIENT_ID`/`BRIGHTSPACE_CLIENT_SECRET`. The
   registered Redirect URI must match `BRIGHTSPACE_OAUTH_REDIRECT_URI`
   exactly, or the OAuth state cookie won't validate.
2. **The course (org unit)** — created however your institution normally
   creates a course offering. `BRIGHTSPACE_ORG_UNIT_ID` points at it.
3. **Groups, for team sync** — a Group Category with named groups (e.g.
   Alpha/Bravo) students are enrolled into. EVOKE reads this at login
   (`_resolve_team_name`) — it does not create groups.
4. **Learners** — nothing EVOKE-specific. Enroll students in the course
   however your institution normally enrolls students (SIS, instructor
   add, whatever's normal). EVOKE has no roster-import step at all — see
   Part 3.
5. **Admin's one-time "Connect Brightspace" click** (`/admin` dashboard)
   — mints the service-connection token the Pull/read actions below use.
   Cached in-process; click again after a server restart or once it
   expires.

---

## Part 2 — Per-mission manual process (repeat for each mission you want live)

This is the actual bottleneck today — two real, separate manual steps:

1. **Create the Dropbox Folder in Brightspace, and publish it.** Someone
   with instructor rights creates the assignment, *and* sets its
   Availability/Visibility so students can actually see it — creating it
   isn't enough. **This is the step that silently breaks submissions if
   skipped**: a folder can exist, be correctly mapped in EVOKE, and be
   visible to the admin/service token, and still 404 for a real student
   submission if this publish step was missed (live-confirmed,
   `BRIGHTSPACE.md`'s 2026-07-21 entry). Check it before assuming a
   `brightspace_sync_failed` row is a code bug.
2. **Pull → Link in `/admin`.** `GET /api/admin/brightspace/assignments`
   is a live, read-only pull + validation (safe to hit repeatedly);
   `POST /api/admin/missions/{id}/link-brightspace` attaches one real
   assignment ID to one EVOKE mission, writing `missions.lms_assignment_ref`
   + a `mission_brightspace_mapping` row. This is where the assignment ID
   actually gets wired to mission content.
3. **Flip `released_at` when ready** (`/admin`'s mission editor) — EVOKE's
   own release gate, deliberately independent of Brightspace's publish
   state. Controls *when players see the mission*; step 1 controls
   *whether submitting to it will actually work* once they do. Both need
   to be true before a mission is genuinely ready.

**Current state**: missions 1–2 have this done (`40`, `41`, both
published, both released). Missions 3–12 still have placeholder
`lms_assignment_ref` values (`mission-03` … `mission-12`) and aren't
released — all 10 need steps 1–2 before they can go live.

---

## Part 3 — Already automatic, no manual step

- **Player creation** — the moment a student clicks "Login with Central
  Registry" and completes Brightspace OAuth, `get_or_create_evoke_player`
  creates their EVOKE account. No admin action, no roster import (the old
  one was deliberately removed).
- **Team assignment** — read from Brightspace Groups at that same login
  (`sync_team_membership`), every time, not a one-time import.
- **Evidence → Brightspace submission** — event-driven
  (`TeamEvidenceSubmitted` → Kafka → the Brightspace Submission Worker),
  fires within moments of a real submission, using the submitting
  student's own token.
- **AI Coach feedback** — same event, independent worker, runs alongside
  the Brightspace push.
- **Grade pull** — `GET /api/admin/brightspace/assignments`'s sibling,
  `admin_sync_grades`, is on-demand today (an admin clicks it per
  mission) — not scheduled, but needs no manual Brightspace-side step
  once clicked.

---

## Part 4 — What could be automated later, and what it'd actually take

For each of the three things this doc gets asked about:

### Assignments — the one worth building first

Brightspace's Valence API supports creating Dropbox Folders
(`POST .../dropbox/folders/`), using the same service-connection token
`list_dropbox_folders` already reads with. This is the most natural of
the three to automate, because EVOKE already owns the mission content —
Brightspace is just where the gradebook entry lives. Concretely:

- New write method in `oauth_providers.py` (`create_dropbox_folder`),
  mirroring `list_dropbox_folders`'s auth pattern.
- **Must explicitly set the folder's availability/visibility at creation
  time, not leave it in whatever default (possibly hidden) state
  Brightspace defaults to** — this is the exact gotcha from Part 2, and
  automating creation without also automating publish just moves the
  same failure mode one step earlier.
- An `/admin` button ("Create in Brightspace") on the mission editor that
  calls it and, on success, writes the mapping directly — collapsing
  today's "create by hand, then Pull → Link" into one click.

### Groups — possible, but a product decision first, not just engineering

The API supports it (`POST .../groupcategories/`, `POST .../groups/`),
but EVOKE currently treats Brightspace Groups as the **source of truth**
for teams — read-only, on purpose. Writing groups back means picking one
direction of truth: either EVOKE-authored teams get pushed to Brightspace
(and an instructor moving a student between Brightspace groups by hand
would need to stay authoritative or get overwritten — a real conflict to
resolve), or it stays read-only and this isn't worth building. Flag this
as a decision before scoping it as work.

### Learners — API-capable, but goes against this app's existing stance

Valence supports enrollment writes
(`POST .../enrollments/orgUnits/{id}/users/`), but this app has an
explicit, considered position against EVOKE managing enrollment: the old
manual roster-import admin UI was **deliberately removed** in favor of
relying on the school's own enrollment process plus automatic
OAuth-login provisioning (see `main.py`'s classlist-pull docstring:
"visibility only, not a reintroduction of the old manual roster-import
flow"). Building this back in would reverse that decision, not extend a
half-finished feature — needs the same "is this actually wanted" check
as Groups, arguably more so since it touches real student enrollment
records outside EVOKE's own data.

---

## Quick diagnostic: submission looks stuck

If a `submissions` row shows `status = 'brightspace_sync_failed'` and the
mapping/token both look right, compare `list_dropbox_folders()` under the
service token vs. that specific student's own token
(`_get_student_token(user_id)`) for the assignment in question. If the
folder is missing from the student's-eye view, it's Part 2 step 1 —
someone needs to publish that assignment in Brightspace. Full writeup:
`BRIGHTSPACE.md`'s 2026-07-21 entry.
