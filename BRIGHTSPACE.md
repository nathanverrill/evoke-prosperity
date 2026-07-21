# BRIGHTSPACE.md

## What has to exist in Brightspace itself for EVOKE to run

Everything below was checked live against the real tenant (`charge.yacenter.org`, org unit `6762`, course "EVOKE Test") on 2026-07-19, not inferred from docs. Two things are real and working; one thing — the actual mission content — doesn't exist yet, and it's a Brightspace-side authoring task, not something EVOKE's code can create for itself.

### Already set up and confirmed live

1. **OAuth 2.0 application registration** (Brightspace's Manage Extensibility admin tool). Gives EVOKE `BRIGHTSPACE_CLIENT_ID`/`BRIGHTSPACE_CLIENT_SECRET`. Its registered **Redirect URI must match `BRIGHTSPACE_OAUTH_REDIRECT_URI` exactly** (`https://evoke.ngrok.app/api/auth/brightspace/callback`) — confirmed the hard way today: starting the OAuth flow from `localhost:8000` instead of `evoke.ngrok.app` produced `Invalid OAuth state`, because the state cookie doesn't cross origins. Scope `core:*:*`. **Working**: real student logins have happened (6 real `evoke_identities` rows), and the admin-side "Connect Brightspace" token grab completed cleanly end-to-end this session.
2. **The course itself** — org unit `6762`, "EVOKE Test," under the "Young Americans Center" tenant. Reachable, real students enrolled (at least the "Bravo Captain" test account).
3. **Groups, for team sync** — `_resolve_team_name` (`evoke/oauth_providers.py`) reads the course's Group Categories/Groups at login time and syncs whichever group a student's enrolled in as their EVOKE team. This is what "Bravo Captain" implies — a group named "Bravo" (or similar) already exists and this account is in it. Not independently re-verified this session, but consistent with the resolved auth work in `GAPS.md`.

### Not set up — this is the actual blocker right now

4. **~~Assignments (Dropbox Folders) — the course has none~~ [SUPERSEDED, 2026-07-21 — see below].** As of 2026-07-19 the course had zero Dropbox Folders. That's no longer true: by 2026-07-21, folders 33–41 exist and are correctly mapped in `mission_brightspace_mapping` for at least missions 1–2 ("Follow the Flow" → 40, "Your Prosperity Origin Story" → 41). But a *new*, more specific blocker replaced it — folder existing and folder mapped isn't the same as folder actually reachable by a student. Read on.

### New finding, 2026-07-21 — a mapped assignment isn't necessarily submittable

Confirmed live, not inferred: submitting real evidence for mission 2 ("Your Prosperity Origin Story," folder `41`) failed with a real `404 Assignment not found` from Brightspace, even though:
- `mission_brightspace_mapping` correctly has `brightspace_assignment_id='41'` for that mission.
- The **admin/service-account token** (`GET /api/admin/brightspace/assignments` path, `_get_service_token`) can see folder `41` fine — it showed up in the live pull, named correctly.

The actual submission call uses the **submitting student's own token** (`_get_student_token`, `workers.py`), not the service account — that's intentional and correct, it's what attributes the grade to the right person in Brightspace's gradebook. Diagnosed by calling `provider.list_dropbox_folders()` with the student's own token directly: it returned **only folder `40`** ("Follow the Flow"). Folder `41` doesn't appear at all for that student, despite existing and being correctly mapped.

**Conclusion: this is a Brightspace-side per-assignment visibility/availability setting** (Availability Dates, Visibility, or a release condition on the Dropbox Folder itself), not anything wrong in EVOKE's mapping, tokens, or submission code. Confirmed mission-1's folder (`40`) doesn't have this problem — it's visible to the student and submissions there sync successfully (`submissions.status = 'brightspace'`).

**What this means practically:** before assuming a submission failure is a code bug, check whether the assignment is actually *published to students* in Brightspace (not just present in the course) — this will block **any** submission to that folder, `team_product` or `individual_evidence` alike, regardless of what EVOKE's own `missions.released_at` gate says. **Action needed in Brightspace itself** (someone with instructor rights): open each mission's Dropbox Folder → check Availability Dates/Visibility → publish it to students. EVOKE's code has no way to detect or work around this from the outside; the 404 is the only signal.

A fast diagnostic for any future case of "student says they submitted but I don't see it in Brightspace": compare `list_dropbox_folders()` under the service token vs. that specific student's own token (`_get_student_token(user_id)`) for the assignment in question. If the folder's missing from the student's-eye view, this is the cause.

### Only needed for the real submission/grading round-trip (not for a playtest)

5. **A service-account application for `BRIGHTSPACE_APP_KEY`/`BRIGHTSPACE_APP_SECRET`.** This is D2L's older ID/Key client-credentials scheme — a *different* registration than the OAuth app in #1, even though both could point at the same tenant. Without it, `evoke/lms/brightspace_lms.py`'s adapter never activates, and every evidence submission silently falls back to the simulator (harmless for a playtest, since evidence still stores correctly either way — just never reaches the real course). **Also needs a code-side follow-up once you have it**: `evoke/docker-compose.yml`'s `web` service environment block doesn't list `BRIGHTSPACE_APP_KEY`/`BRIGHTSPACE_APP_SECRET` at all today, so setting them in `.env` alone wouldn't be enough — the compose file needs those two lines added too.
6. **Worth double-checking once real creds exist**: the service-account token request (`get_service_account_token`, `brightspace_lms.py`) asks for scope `"awards:_:_ courses:_:_"` — no explicit dropbox/submission scope. Untested against a real tenant; may need widening before `submit_assignment`/`get_submissions_for_assignment` actually succeed permission-wise.
7. **A grade webhook subscription**, if you want Brightspace to push grades back automatically (`POST /api/webhooks/brightspace/grade`) instead of relying on the backup polling job. How this gets configured on D2L's side (Data Hub push, Intelligent Agent, or similar) wasn't investigated this session — only relevant once real submissions are flowing.

### Not needed — a different, unused path

LTI 1.3 (`BRIGHTSPACE_LTI_CLIENT_ID`/`BRIGHTSPACE_LTI_PUBLIC_KEY`) is a second, alternate login mechanism (platform-initiated launch) that this deployment isn't using — the OAuth login button is what's actually wired up and proven live. Nothing to set up here unless you specifically want a "Launch EVOKE" button inside Brightspace itself.

---

## Two separate identity systems, on purpose

EVOKE has two logins that never share an identity:

1. **Real students/instructors** — Brightspace OAuth (`AUTH_PROVIDER=brightspace`) or LTI 1.3 launch. Every user this creates is a Brightspace account underneath (`evoke_identities.brightspace_user_id`).
2. **Evoke Admin** — `POST /api/admin/login`, username + bcrypt password (`EVOKE_ADMIN_PASSWORD_HASH`). Creates its own `users` row (`<username>@evoke.local`, `role='admin'`), with **no** `evoke_identities` row and no Brightspace account behind it at all.

`/admin` (a standalone static page, `evoke/static/admin/`, mounted at that path on the same FastAPI process/port as everything else) only ever talks to path #2. Signing into it never requires a Brightspace account, a Brightspace login, or any Brightspace token — verified directly in the route code (`admin_login`, `evoke/main.py`), which does nothing but check the password hash and mint a session.

This matters because `#/admin`'s old incarnation (the unused `v2/` build) never had its own login at all — it just inherited whatever session was already active. `/admin` today is a deliberately separate front door.

---

## Why the Mission Sync button still needs *a* Brightspace credential

Signing into `/admin` doesn't need Brightspace. **Pulling real assignment data out of Brightspace does** — that's unavoidable, you can't read Brightspace's data without Brightspace's permission. The design question was never "can we avoid this," it's "does needing it for one button contaminate the admin account's login." It doesn't:

- `_test_brightspace_tokens: dict` (`evoke/main.py:75`) is a process-memory cache of `{evoke_user_id: access_token}`.
- A real learner/instructor OAuth login (`auth_brightspace_callback`) populates this for *their own* user_id as a side effect of logging in normally.
- The Evoke Admin's user_id is a completely different row, so it never appears in that cache just by logging into `/admin`.

**`GET /api/admin/brightspace/connect`** (admin-gated) exists to get a token into that cache *for the admin's own session*, without creating a second identity:

1. Admin clicks "Connect Brightspace" in the `/admin` dashboard → full-page redirect to `/api/admin/brightspace/connect`.
2. That route mints a random `state`, stores it in an `admin_oauth_state` cookie (distinct from the learner flow's `oauth_state` cookie — the two can coexist in the same browser), and redirects to Brightspace's real authorize URL.
3. The admin (or whoever's driving the browser) authenticates to Brightspace as themselves — same login screen a student sees, same tenant (`charge.yacenter.org`), no new app registration needed.
4. Brightspace redirects back to the **same** registered callback URL every login uses, `/api/auth/brightspace/callback` (`auth_brightspace_callback`, `evoke/main.py:792`). That function now checks `admin_oauth_state` *before* anything else:
   - **Cookie present and matches `state`** → this is a token-only connect. Reads the *already-logged-in* admin's id straight off the existing `evoke_session` cookie (`get_current_admin(request)`, called directly, not just as a route dependency), exchanges the code for an access token, caches it as `_test_brightspace_tokens[admin_id] = token`, deletes the `admin_oauth_state` cookie, redirects to `/admin/`. **No new session is issued, no EVOKE Player is provisioned** — the admin's login is untouched.
   - **Cookie absent** → falls through to the normal path: provisions/finds an EVOKE Player, syncs team from Brightspace Groups, issues a real learner/instructor session. This is the path every actual student login takes.

Same URL, same registered redirect, branched entirely by which state cookie shows up — so no second Brightspace redirect-URI registration was needed to add this.

Once connected, **`GET /api/admin/brightspace/assignments`** (`evoke/main.py:~1340`) uses that cached token to call `list_dropbox_folders` against the real tenant, validates each row (missing ID/name → error, duplicate ID in the same pull → error, already-mapped → flagged separately), and returns everything to the browser. **Nothing is written to the database by this call** — safe to hit repeatedly while reviewing.

---

## The rest of the flow: mission-first, then link

An Evoke mission is the container for exactly **one** Brightspace assignment — creating the mission always comes first, linking it to Brightspace is a separate step attached to a mission that already exists. Not the other way around: pulling assignments never creates missions by itself.

1. **Create** (`POST /api/admin/missions`) — title required, every curriculum field (Arc, Superpower, Skills, PFL Domain, Week, brief/narrative/evidence) optional at creation time. `lms_assignment_ref` starts `NULL`. This is a pure Postgres write; Brightspace is never involved in creating a mission.
2. **Connect** (above) — one token, cached for this admin session only, needed only to pull real assignment data. Expires whenever the process cache is cleared (restart) or the token itself expires; just click Connect again.
3. **Pull** (`GET /api/admin/brightspace/assignments`) — live read-only fetch + validation, renders a table. Each unlinked, valid row gets a "link to mission" picker, populated from missions that don't have a Brightspace link yet. **Nothing is written by pulling.**
4. **Link** (`POST /api/admin/missions/{id}/link-brightspace`) — attaches one assignment ID to one already-created mission. Writes `missions.lms_assignment_ref` and a `mission_brightspace_mapping` row (the same table `brightspace_lms.py` reads from for real evidence submission/grading). **True 1:1, enforced at the database level in both directions**, not just application logic: `missions` already had `UNIQUE(campaign_id, lms_assignment_ref)`; `mission_brightspace_mapping` now also has `UNIQUE(campaign_id, brightspace_assignment_id)` (`idx_mission_brightspace_mapping_assignment`, added both to `init-db.sql` for fresh installs and as idempotent startup DDL for the already-deployed instance). Trying to link an assignment that's already linked to a *different* mission 409s, naming which mission has it, rather than silently stealing the link.
5. **Edit** (`PUT /api/admin/missions/{id}`) — Arc, Superpower, Primary/Secondary Skill, PFL Domain, Week, Mission Brief, "Your Mission" narrative, Evidence checklist. Pure Postgres write, **zero Brightspace calls** — this is what makes ongoing mission authoring independent of live connectivity, whether or not the mission has been linked to Brightspace yet.

**Explicitly out of scope:** Minecraft quests (`mc_quests`). Despite `mc_quests.mission_id` existing as a nullable FK in the schema (used only to show a quest badge on a mission card in the learner-facing progress map), quests are an independently-authored system (in-world, via datapacks/scoreboards) and this sync flow never creates, edits, or depends on them.

---

## The other direction: a student's evidence reaching Brightspace

Once a mission is linked (above) and a student has a Brightspace identity (automatic at login), submitting evidence can push that submission into the real Brightspace dropbox. This is **event-based, not a live call inside the submit request**:

1. `POST /api/submit-evidence` (`evoke/main.py`) stores the file in MinIO and the `submissions` row, then publishes `TeamEvidenceSubmitted` (`submission_id`, `user_id`, `mission_id`, `object_key`, `filename`, `team_members`) and returns — the student's response never waits on Brightspace.
2. `evoke/workers.py`'s **BRIGHTSPACE SUBMISSION WORKER** (`_process_event`, consuming the same Kafka stream the AI Coach Worker and every other worker already read from) picks up that event: resolves the student's `brightspace_user_id` (`evoke_identities`) and the mission's `brightspace_assignment_id` (`mission_brightspace_mapping`), fetches the file back out of MinIO, and pushes it — via the real `BrightspaceLMS` adapter if configured, else the same `brightspace-sim` fallback the old inline code used.
3. On success, `submissions.brightspace_submission_id` is stamped so the existing grade-sync/webhook path can find it later.

This mirrors the exact reasoning already applied to AI Coach feedback (`workers.py`'s comment on the old `trigger_ai_review`) and the Field Report's Word of Wisdom generation: a live external network call has no business blocking a learner-facing HTTP response, and moving it into the worker that already exists for that event was strictly less new surface area than adding a second one.

**What this doesn't add:** retries. If the push fails (bad token, Brightspace down, mission not linked, student not Brightspace-identified), it's logged and dropped — same "continue anyway, stored locally" behavior as before, just relocated. If that turns out to matter in practice, `evoke-minecraft-bridge/bridge.py`'s `offline_delivery_loop` (which retries reward delivery to players who were offline at delivery time) is the closest existing precedent for a periodic catch-up pass.

### `submissions.status`

A real progression now, not just a value written once at insert and never touched again:

`submitted` → `brightspace` / `brightspace_sync_failed` (set by the Brightspace Submission Worker above) → `graded` (set by the grade webhook or the backup polling job, once Brightspace itself confirms a grade — which can only happen for a row that already reached `brightspace`, so this really is the terminal state).

Seeing `brightspace_sync_failed` on a row that looks correctly mapped? Check the new finding above (2026-07-21) before assuming a code bug — a real, live-confirmed cause is the assignment simply not being published/visible to that student in Brightspace yet, which 404s regardless of how correct the mapping and tokens are.

**AI review is deliberately not a value in this column.** It's an independent, concurrent branch off the same `TeamEvidenceSubmitted` event (the AI Coach Worker, running alongside the Brightspace Submission Worker, not before or after it) — the two can finish in either order. Folding "ai_reviewed" into one linear status would sometimes misrepresent what actually happened (e.g. a fast Brightspace sync completing before a slower AI pass would make the AI step's write look like a regression). AI review already has its own correct, independent, timestamped record — an `awards` row with `tier='epic', source='ai_review'` — and stays there.

---

## How this fits the rest of the identity chain

For reference, the full chain from "someone logs in" to "a Minecraft whitelist entry exists" — none of it required new plumbing except the whitelist step:

| Step | Where it happens | Trigger |
|---|---|---|
| EVOKE user ↔ Brightspace user id | `evoke_identities.brightspace_user_id` | Automatic, every real login (OAuth or LTI), via `get_or_create_evoke_player` |
| EVOKE user ↔ team | `sync_team_membership`, from Brightspace Groups | Automatic, at OAuth login (`oauth_providers.py::_resolve_team_name`) |
| EVOKE user ↔ Minecraft username | `minecraft_links` | Two-channel link-code flow (student types code in-game, confirms on web/phone) |
| Minecraft whitelist entry | `evoke-minecraft-bridge/bridge.py`, `whitelist add <username>` via RCON | The `MinecraftLinked` event, fired the moment the link above is confirmed |
| Mission ↔ Brightspace assignment | `mission_brightspace_mapping` | Admin-reviewed import, described above — not automatic, by design (nothing writes to the live mission catalog without a human looking at it first) |

Only the last two rows are new as of this pass. The rest already existed and needed no changes.
