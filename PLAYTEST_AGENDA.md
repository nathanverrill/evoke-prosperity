# EVOKE × Brightspace Playtest — Overview & Agenda

**Date:** July 2026 &nbsp;·&nbsp; **Duration:** ~60 minutes &nbsp;·&nbsp; **Focus:** Website ↔ Brightspace round trip

## Goal

Prove the core loop works for a real student account:
**log in → play a mission → submit evidence → teacher grades in Brightspace → student sees feedback.**

Minecraft is out of scope and hidden for this playtest (kill-switch in `controller.js`; flip `MINECRAFT_ENABLED` back to `true` afterward).

## Before the session (facilitator checklist)

- [ ] Test student accounts exist in Brightspace and are placed in **groups** (a student with no group cannot submit — the backend requires team membership)
- [ ] Missions are **released** and mapped to Brightspace assignments (Admin → Mission Sync)
- [ ] Each tester can reach the EVOKE site URL from their device
- [ ] One facilitator has Brightspace grading access for the course

## Agenda

| Time | Activity |
|------|----------|
| 0:00–0:05 | Welcome, goals, what we're testing (and not testing) |
| 0:05–0:15 | **Login** — each tester signs in through Brightspace; confirm they land on their own EVOKE account with the right name |
| 0:15–0:30 | **Play Mission 1** — read the story/novel pages, review the assignment brief, reach Operations Hub |
| 0:30–0:40 | **Submit evidence** — Ops Hub → *Submit My Findings*: take/choose a photo, write an observation, confirm submit. Verify the "Field Evidence Filed" state and the PDF link |
| 0:40–0:50 | **Grade** — facilitator opens the Brightspace dropbox, confirms each student's Field Evidence PDF arrived under their own name, enters a grade + feedback comment |
| 0:50–0:55 | **Feedback** — students return to EVOKE and confirm the graded result/feedback is visible to them |
| 0:55–1:00 | Debrief: what broke, what confused, what's missing |

## What to watch for

- Login lands on the **wrong person's account** (shared-computer session leak — log out fully between testers)
- Evidence PDF missing or attributed to the wrong student in Brightspace
- Submission errors ("You're not on a team yet" = group missing in Brightspace)
- Grade entered but feedback never appears on the EVOKE side
- Any Minecraft content still visible anywhere (should be none)
- B1llBot AI chat may still mention Minecraft — its persona wasn't changed, only the site UI

## Capture

For every issue: who, which screen, what they did, what they expected, screenshot if possible.
