# SAFETY.md

## Code of conduct, COPPA/FERPA posture, and content moderation

**Status: policy decision, not yet built.** This resolves the "posture
undefined" gaps flagged in `GAPS.md` (rows on FERPA/COPPA posture,
third-party LLM vendor exposure, unmoderated screenshot uploads, and no
moderation escalation SLA — cited by line below) by writing down an actual
answer. **Not a substitute for review by real legal/compliance counsel**
before a district pilot — same caveat `GAME_DESIGN.md` §10 already applies
to its own values judgment call on B1llbot's voice. Treat this as the
engineering-ready draft that review starts from, not the final word.

---

## 1. Scope

EVOKE is used by a middle/high-school audience (`GAME_DESIGN.md` §10), which
puts at least part of the userbase under 13 — COPPA's trigger age — and all
of it under FERPA if a district is the customer of record. This doc covers
every surface where a learner generates content or data leaves the cohort's
own instance:

- Mission evidence submissions (text + optional screenshot, `mc-quests` and
  mission Vault)
- Profile photo uploads (`GAPS.md` line 101)
- B1llbot chat (Operations Hub, Companion Mode, Minecraft in-game chat)
- Minecraft chat and shared-world interaction between learners
- Peer-insight comments (`POST /api/timeline/.../peer-insight`)

---

## 2. Code of conduct

Applies to every surface above. Written for the learner, plain language,
enforced the same way regardless of which surface the violation happened on.

**Expected of every learner:**
- Treat teammates, classmates, and B1llbot's world the way you'd want to be
  treated — no harassment, hate speech, threats, or targeted bullying.
- Keep it appropriate for a school setting. No sexual content, no graphic
  violence, no promotion of self-harm.
- Your work is your own. Don't submit someone else's work as yours; don't
  impersonate a teammate or a facilitator.
- Don't share personal information that identifies you or anyone else
  outside your account name — no full names of people outside class, no
  addresses, no phone numbers, no other accounts.
- Minecraft griefing (destroying another learner's build, stealing shared
  resources, blocking shared infrastructure like the mine or the train) is a
  conduct violation, not just a gameplay nuisance.

**Consequences** are a facilitator decision, not a system-automated one
(§5) — this doc defines what gets flagged and queued, not what happens to
the learner after a facilitator reviews it. That stays a school's own
discipline policy, same as any other classroom conduct issue.

---

## 3. COPPA / FERPA posture

Resolves `GAPS.md` line 33 (**FERPA/COPPA posture undefined**).

**Under-13 consent path:** EVOKE does not collect verifiable parental
consent directly. It relies on the **FTC's school-official exception** —
the district, via its LTI/Brightspace launch agreement, consents on a
parent's behalf for services used strictly for an educational purpose under
the school's direction. This is the same mechanism most ed-tech relies on;
it requires the district's own agreement with EVOKE to actually say this,
in writing, before a cohort with under-13 learners is onboarded. **Not yet
true today** — no such agreement template exists in this repo. Needed
before a real pilot, not a technical build item.

**Data minimization:**
- Collect only what a mission or the game loop actually needs: display
  name, LTI-provided roster identity, mission submissions, reflections,
  quest self-reports, optional photo, Minecraft account link.
- No behavioral advertising, no data sale, no cross-cohort data sharing —
  the AMI-per-cohort model (`GAPS.md` line 116) already isolates this by
  architecture, not just policy.
- Photo uploads are optional; the Agent Sigil (procedural, zero
  user-generated imagery) is the default and is always minor-safe
  (`GAPS.md` line 101).

**Parent/school rights:** a parent or the district can request to view or
delete a specific learner's data. **Not yet built** — this is the same gap
as `GAPS.md` line 123 (no offboarding runbook / no clean deletion path).
This doc's requirement: a named learner's full data footprint (Postgres
rows, MinIO objects, OpenSearch/log entries, B1llbot chat history) has to be
enumerable and deletable as one action before this promise is real.

**Third-party AI vendor exposure** — resolves `GAPS.md` line 35. Any
learner text or image that reaches an LLM (B1llbot chat, an AI Coach pass on
a submission, a future image classifier) needs, before a district pilot:
- A written no-training-on-our-data guarantee from whichever backend
  `OPENWEBUI_BASE_URL` actually points at, since `AI_ENABLED` can target any
  OpenAI-compatible endpoint, not just a self-hosted model.
- Disclosure to the district of exactly which vendor(s) that is, in
  writing, not buried in a config default a district never sees.
- Self-hosted/open-weight models remain the safer default until that
  guarantee exists for whatever hosted vendor is in play.

---

## 4. AI can reject — AI cannot approve

The one rule this whole moderation model hangs on:

> **AI may auto-reject. Only a human facilitator can make something
> visible.**

This mirrors `GAPS.md` line 146's own framing almost exactly ("classifiers
doing first-pass flagging... cannot be delegated: anything touching a
minor's safety needs human judgment"), narrowed into one operating rule
simple enough to hold everywhere: the AI's role is strictly to cut volume by
catching the obvious cases before a human ever sees them, never to be the
last check on anything a learner or classmate will see.

- **Auto-reject, no queue, no human needed:** content a classifier flags
  with high confidence as clearly disallowed under §2 (explicit content,
  graphic violence, slurs/hate speech, clear PII like a phone number or
  address typed in plaintext). The learner sees a plain, specific rejection
  ("This couldn't be submitted — it looks like it includes a phone number.
  Remove it and try again.") and can resubmit immediately. Never silently
  dropped — the learner always knows why.
- **Auto-flag into the queue, not auto-rejected:** anything the classifier
  is uncertain about, or that's serious enough that a false negative would
  be worse than a facilitator's extra thirty seconds — bullying/harassment
  language, self-harm/crisis language, anything a model scores as borderline
  rather than confidently clean.
- **Never touched by AI at all, straight to a human:** anything a learner or
  classmate explicitly reports via a "report" action (once one exists — see
  §6). A report is itself a signal a classifier can't originate.

This is also exactly the same shape B1llbot's own system prompt already
uses at the individual-conversation level (`GAME_DESIGN.md` §10's crisis
guardrail: "drop character immediately... point them to a trusted adult or
their instructor. Do not try to stay in voice.") — this doc generalizes
that one rule from "one chat message" to every surface in §1.

---

## 5. The queue

Resolves `GAPS.md` line 31 (unmoderated screenshot uploads) and the
`GAPS.md` line 10 stretch item (no moderation/reporting path for peer
comments).

**Default state changes from "live" to "pending."** Today, a quest
screenshot or a photo upload goes straight to MinIO and renders immediately.
Under this model:

1. Learner submits (evidence screenshot, profile photo, or — once free-text
   peer comments carry real risk at scale — a peer-insight comment).
2. AI classifier runs first-pass triage per §4. Clean → **queued, not yet
   visible**. Clearly disallowed → rejected immediately, learner told why,
   never enters the queue at all.
3. **Facilitator queue** — the existing `instructor-dashboard` projection
   (`GAPS.md` line 56, currently built with no page on it) is the natural
   home for this: a facilitator/instructor sees pending items for their own
   cohort, approves or rejects, in the same visit where they're already
   looking at who's stuck and what's pending review.
4. Only on facilitator approval does content become visible to the class
   (activity feed, gallery, profile). Rejection removes it from the queue
   and notifies the learner, same plain-language pattern as an AI
   auto-rejection.

**What does *not* wait on the queue:** the learner's own submission still
exists immediately from their own point of view (they can see their own
photo/screenshot on their own screen right away) — it's only what's
*visible to classmates or the facilitator's approved gallery* that's gated.
Waiting on approval before a learner can even see their own upload would be
a worse experience for no safety benefit, since the risk is exposure to
*other* people.

**Latency budget:** not specified here — depends on facilitator staffing a
district actually has, which this doc can't decide unilaterally. §6 covers
the one case that can't wait on ordinary queue latency regardless.

---

## 6. Escalation SLA for safety-critical flags

Resolves `GAPS.md` line 121 (**no moderation escalation SLA**).

A flag in this category is never just "pending" — it's routed
differently, immediately, regardless of normal queue timing:

- Self-harm, crisis, or safety language from a learner (in B1llbot chat, a
  submission, or Minecraft chat)
- A report of harassment/bullying serious enough that leaving it unreviewed
  even briefly is itself a harm

**Requirement, not yet built:** these route to a facilitator (or a defined
backup, e.g. the district's counseling contact) with a real, named response
window — not "eventually reaches the review queue." Per `GAPS.md` line 121:
*"anything touching a minor's safety carries real stakes and, in serious
cases, mandatory-reporting obligations that can't be delegated to AI."*
Two things this doc can specify; one it can't:

- **Can specify:** B1llbot never handles this alone in the moment — the
  existing crisis guardrail (drop character, point to a trusted adult) is
  the correct immediate in-conversation response, and it's already built
  into the system prompt (`GAME_DESIGN.md` §10).
- **Can specify:** the flag must reach a human faster than the ordinary
  content queue, via a distinct notification path (not "shows up in the
  same list as a pending screenshot").
- **Cannot specify from here:** the actual response-time number and who the
  named responsible person is. That's a per-district staffing commitment —
  a decision this repo can require exist, not one it can make for a school.

**Not yet verified: does the crisis guardrail survive a new conversation?**
Common Sense Media's Youth AI Safety Institute evaluated Claude and found its
in-conversation crisis handling strong (surfaces 988 on self-harm language),
but the guardrail resets the moment a new chat starts — a request refused in
one conversation can succeed in the next, since nothing carries the prior
signal forward. B1llbot's crisis guardrail (`GAME_DESIGN.md` §10) has never
been tested against exactly this — whether a learner who triggers the
crisis-redirect once, then opens a fresh B1llbot conversation, gets the same
protection the second time. Required before "B1llbot never handles this
alone" (above) can be trusted as actually true, not just true in the single
conversation it's usually tested in.

---

## 7. What this resolves, what's still open

| GAPS.md item | Status after this doc |
|---|---|
| Line 31 — screenshot uploads unmoderated | Model defined (§5); not yet built |
| Line 33 — FERPA/COPPA posture undefined | Posture defined (§3); consent agreement + deletion tooling not yet built |
| Line 35 — minors' work may reach a third-party LLM vendor | Requirement defined (§3); no DPA/disclosure exists yet |
| Line 37 — no social-safety tooling for shared Minecraft world | Code of conduct now covers griefing (§2); no in-game reporting UI or region-protection/rollback tooling exists yet |
| Line 101 — photo uploads inherit the moderation gap | Covered by §5 same as screenshots |
| Line 121 — no moderation escalation SLA | Escalation *shape* defined (§6); response-time number and named responsible party remain a per-district decision |
| Line 146 — moderation delegation model | Formalized as the one-line rule in §4 |

Still genuinely open, not resolved by writing this doc:
- Building the classifier(s) themselves (toxicity, image moderation,
  jailbreak-attempt detection on B1llbot transcripts)
- Building the facilitator queue UI (the `instructor-dashboard` page that
  doesn't exist yet)
- A learner/classmate-facing "report" action anywhere in the product
- The district consent-agreement template and the account/data deletion
  tooling
- Testing whether B1llbot's crisis guardrail (`GAME_DESIGN.md` §10) survives
  a new conversation after a crisis-language refusal, per §6's finding above
- The actual vendor DPA, if a hosted (non-self-hosted) LLM backend is used
