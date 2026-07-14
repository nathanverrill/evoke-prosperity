# docs/ index

This folder is organized into three parts, reflecting what is authoritative versus historical.

## `canon/`

The current source of truth for the EVOKE Prosperity story, curriculum, and platform design philosophy. If something elsewhere conflicts with these files, these files win.

- `overview.md` — product design & experience spec (missions, XP, badges, teams, etc.)
- `1.jpg`–`5.jpg` — the five narrative infographics (story bible): Keel/Halyard/Oasis, Alpha Dynamics' withdrawal, the Brokers, the rebuild, the EVOKE Network invitation
- `stakeholderfeedback.md` — story-consultant review of the five infographics against the 7-point story structure; identifies gaps (Alex's backstory, Broker antagonist motivation, missing Pinch Point Two) and proposes a 36–42 page / 6-weekly-chapter structure
- `narative-literacy-mapping.md` — maps each infographic to a financial-literacy concept and defines B1llbot's voice/personality; also revises the ending (resilience over "problems solved") and de-moralizes the Oasis/Halyard/Keel hierarchy
- `billslifeprinciples.pdf` — Bill Reynolds' personal life-philosophy essay; the direct real-world source for B1llbot's character and worldview
- `Prosperity Campaign Missions -- 07.14.26.docx.txt` — the 12-mission, 6-week curriculum in narrative/prose form (student-facing mission text — the "Evoke Mission (direct to students)" framing, Step 1/2/3 structure, and Evidence checklist per mission). **This is the version actually transcribed into the running app** (`brightspace-sim/brightspace_api.py`'s per-mission `CustomFields`, synced into `missions.pbl_description`/`evidence_requirements_md`, rendered on the mission-brief screen) — see `GAPS.md`'s "Real mission content populated" entry. The 06.11.26 version is superseded; it's in `legacy/` now, not here.
- `Evoke 12 Mission Detailed Summary revision bf v2.xlsx - Google Sheets.pdf` — the same 12 missions in structured table form (good source for seeding a missions data model) — **not yet reconciled against the newer 07.14.26 docx**; if the two disagree on anything, the docx is what's actually live.
- `thread4.md` — platform design philosophy: EVOKE as a transmedia experience (Operations Hub, Basin Simulation, B1llbot as field guide), not an LMS
- `thread5.md` — Minecraft as a strictly optional side-quest layer, never required for grades
- `thread6.md` — accessibility/deployment model: 4-level engagement ladder so schools with no tech can still run the full curriculum

## `legacy/`

Superseded draft material, kept for historical context only — **not canon**. Contradicts current canon in specific ways (see below) and should not inform current work unless the team explicitly revives it.

- `All NPC and World Prompts/` — an earlier draft of the Minecraft world and its in-game LLM prompts. Built around a different premise: Alpha Dynamics still actively runs Keel as an extractive company town, and Alex is secretly Alpha's former CEO with amnesia. This conflicts with current canon, where Alpha has withdrawn from the mountain and "the Brokers" fill the power vacuum, and Alex has no CEO backstory.
- `Prosperity Campaign Missions -- 06.11.26 .docx.txt` — an earlier draft of the 12-mission curriculum, superseded by `canon/Prosperity Campaign Missions -- 07.14.26.docx.txt` (moved here 2026-07-16). Meaningfully thinner than the newer version — no Step 1/2/3 structure, no explicit Evidence checklist per mission — don't use this one as a source for anything mission-content-related.

## `process/`

Meeting notes and planning conversations — useful project history and open action items, but not narrative or curriculum canon.

- `7-10-meeting-minutes.md` — 2026-07-10 team meeting: UI/UX walkthrough, LMS integration ownership (Evoke vs. Anna/YAB), open questions on individual vs. team submissions, action items. **The individual-vs-team-submissions question is resolved now** (2026-07-16): a mission's evidence is one shared team artifact, each member's own required reflection is what actually gates their award/XP — see `GAPS.md`'s "No team-level play" entry. This is the meeting notes' own historical record, left as-written rather than edited after the fact.
- `thread1.md` — early infrastructure/event-architecture planning (Redpanda, MinIO, Postgres, OpenSearch, Keycloak). Keycloak specifically was never actually built — the real system has no real auth today (see `GAPS.md`: "Auth is dev-grade outside LTI"), just LTI 1.3 auto-provisioning and an unprotected `/api/admin/*`.
- `thread2.md` — Minecraft technical integration planning (account linking, Geyser/Bedrock cross-play, accessibility)
- `thread3.md` — Brightspace (D2L) LMS API integration research (OAuth, Award Service, Groups)

## `build-history/`

Not part of the canon/legacy/process taxonomy above — a separate, much larger archive of dated build-progress logs (task-complete summaries, week summaries, setup guides from earlier build passes) generated during active development. Genuinely historical by nature (a progress log doesn't get "updated," it gets superseded by a new entry), not curated or indexed here, and **not a reliable source for current state** — `GAPS.md` is. Worth a `grep` if you need the history of *how* something was built, not whether it still works that way.
