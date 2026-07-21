# COMPLIANCE_TODO.md

## What actually has to happen for EVOKE to be compliant

Synthesizes `SAFETY.md`, the published Minor Safety & Legal Requirements
checklist artifact, and the Colorado-specific findings from this thread into
one sequenced action list. Scoped to the real pilot: a **Colorado Middle
School Pilot** (`docs/process/thread2.md`), which means the under-13
population isn't an edge case here — it's a meaningful share of actual
users, so COPPA and the Colorado Student Data Transparency and Security Act
are both live requirements, not hypotheticals.

**Not legal advice** — same caveat as `SAFETY.md` and the checklist
artifact. Have actual counsel review before treating anything here as a
sign-off, especially the paperwork items.

**Priority is about sequencing, not just severity** — P0 items are blocking
because something later depends on them (you can't scope a moderation queue
before deciding the consent path that determines what data legally exists
to moderate). P1 items are real requirements that don't block a first
careful, small pilot. P2 is ongoing process, never "done."

**Every item below is now tagged with the specific law it satisfies** —
`[COPPA]`, `[FERPA]`, `[CIPA]`, `[CO-SDTSA]`, `[CO-CPA]`, `[CO-AI]`,
`[CSAM]`, `[CO-BREACH]` — after a pass that checked this list against the
regulations themselves (live sources, current status), not just against
this repo's own prior notes. The table right below is the same information
read a different way: one row per law, not one row per action, so it's
possible to answer "are we actually covering FERPA" without reading the
whole list end to end.

---

## Regulatory checklist, by law

| Law | What it actually requires | Status |
|---|---|---|
| **COPPA** (16 CFR Part 312, amended rule — compliance deadline April 22, 2026, already past) | Verifiable parental consent *or* the FTC school-official exception, invoked in writing per district; data minimization; a **written retention-limit policy** (new in the amended rule); an **annual security risk assessment** (new); a real deletion path | Consent path: ⏳ decided informally, not written down. Retention policy: ❌ none exists. Risk assessment: ❌ none exists. Deletion path: ⏳ designed (single-footprint deletion item below), not built. |
| **FERPA** (34 CFR Part 99, the *separate* school-official exception — easy to conflate with COPPA's, checked to confirm it isn't) | A data agreement that **explicitly invokes 34 CFR § 99.31(a)(1)**, not a generic ToS; the district retains direct control over education records; no redisclosure beyond the agreement's stated purpose; the district names EVOKE in its own annual FERPA notification | ⏳ The NDPA (below, under CO-SDTSA) likely covers this, but it hasn't been specifically confirmed that the signed exhibit contains FERPA-invoking language, not just Colorado-specific terms. New checklist item added below — this was previously not tracked as its own requirement anywhere in this repo. |
| **CIPA** (47 U.S.C. § 254(h) — the *district's* E-rate certification; EVOKE's obligation is not to undermine it) | District-side: an internet safety policy, content filtering, and monitoring of minors' online activity, including in chat/direct messaging. EVOKE-side: don't be the reason a certified district's policy is no longer true | ❌ `WHITELIST.md`'s confirmed findings (open server, no whitelist, no chat-disable mechanism) are in direct tension with a district's own CIPA certification around "safety of minors... in chat rooms and direct electronic communications." Not previously connected to CIPA explicitly anywhere in this repo. |
| **Colorado SDTSA** (C.R.S. §§ 22-16-101–113) | The NDPA + Colorado exhibit with the pilot district; no sale of student data (already true); public disclosure of what's collected | ⏳ NDPA unsigned. Public-disclosure posting not confirmed built. |
| **Colorado Privacy Act** (as amended by SB 24-041, effective October 1, 2025) | Opt-in consent for a *known minor* (13–17) before: targeted advertising, sale, profiling with significant consequences, extended retention, or **design features that significantly increase, sustain, or extend a minor's use** | Ads/sale/profiling: likely N/A, needs to be written down. Extended retention: open (ties to the COPPA retention item). **Design features**: genuinely open — EVOKE's streak/XP/badge/Team Wheel mechanics are gamification built to sustain engagement; whether the statute reaches them hasn't been asked of counsel. |
| **Colorado AI Act** (SB 26-189, replacing SB 24-205, effective January 1, 2027 — not yet enforceable) | Disclosure/technical documentation for automated systems that materially influence a "consequential decision"; education examples given include automated grading | Not yet due. B1llBot's no-grading design rule is a real argument for staying out of scope; the AI COACH WORKER's automated epic-tier award is a closer call, not yet reviewed by counsel. |
| **CSAM reporting** (18 U.S.C. § 2258A, as amended by the 2024 REPORT Act) | Report apparent CSAM to NCMEC's CyberTipline on actual knowledge; preserve reported material for **one year** (raised from 90 days) | ❌ No hash-matching wired in. ❌ No written reporting process/named owner. Retention tooling doesn't yet account for the 1-year preservation floor. |
| **Colorado breach notification** (C.R.S. § 6-1-716) | 30-day notification to affected Colorado residents; Attorney General notification at 500+ affected residents | ❌ No runbook written; no named responsible party. |

---

## P0 — Blocking before any real student data is collected

- [ ] `[CO-SDTSA]` **Sign a Colorado Student Data Transparency and Security
      Act agreement with the pilot district** (C.R.S. §§ 22-16-101–113) — the
      multi-state Student Data Privacy Consortium's National Data Privacy
      Agreement (NDPA) plus Colorado's exhibit, confirmed as the actual
      mechanism CO districts use (SDPC's registry at `privacy.a4l.org`, 275,000+
      signed agreements to date) — not a custom contract. Worth knowing there
      is no separate state or federal "approved AI model/vendor whitelist" to
      check against instead — CDE has not issued its own AI policy (its
      Colorado Roadmap for AI in K-12 Education is voluntary guidance, not a
      mandate); the NDPA/exhibit *is* the compliance mechanism, not a
      substitute for one.
- [ ] `[FERPA]` **Confirm the signed NDPA exhibit actually invokes FERPA's
      school-official exception (34 CFR § 99.31(a)(1)), not just Colorado's
      state-law terms.** New this pass — FERPA was previously only named in
      passing in this repo ("COPPA/FERPA posture"), never checked as its
      own requirement. FERPA and COPPA each have their *own* school-official
      exception, easy to conflate; a generic terms-of-service agreement
      satisfies neither. The SDPC NDPA template likely covers this, but
      "likely" isn't a verified answer — read the actual signed document
      once it exists, don't assume the template did the work.
- [ ] **Test whether B1llbot can recognize an escalating distress pattern
      across a single sitting.** Common Sense Media's Youth AI Safety
      Institute found Claude's in-conversation crisis handling strong but
      resettable across a *new* conversation. Reconciled against
      `GUARDRAILS_PLAN.md`'s Phase 0/1 build (`SAFETY.md` §6 has the full
      writeup): that specific failure mode doesn't apply to B1llbot, since
      `billbot_chat()` sends no conversation history at all — there's no
      cross-conversation state to reset because there's no cross-*message*
      state either. The live-tested regression this surfaced was worse and
      is now fixed: the gateway's content filter was blocking crisis-language
      messages before B1llbot ever saw them, replacing the required
      crisis-redirect with a generic error. What's still genuinely untested
      is the escalating-pattern case (message 1 raises concern, message 3
      confirms it, but each is evaluated in isolation) — still blocking,
      same reasoning as the LLM no-training item below, just a narrower
      question than originally framed.
- [ ] `[COPPA]` **Decide and document the COPPA consent path per cohort**
      — for this pilot specifically, that's the FTC school-official
      exception via the same district agreement above (COPPA's *own*
      version of that exception, distinct from FERPA's above — same name,
      two different regulations, two different agreements to check), not
      verifiable parental consent collected directly. Put this in writing;
      don't leave it implicit.
- [ ] `[CSAM]` **Wire CSAM hash-matching (e.g. PhotoDNA) into every
      photo-upload path** before storage. Blocking because photo upload is
      already a shipped feature today — this isn't a future-feature gate,
      it's an existing gap on a live upload surface.
- [ ] `[CSAM]` **Write the NCMEC CyberTipline reporting process and name an owner**
      — needs to exist on paper before automated detection is even fully
      tuned; the legal duty (18 U.S.C. § 2258A) doesn't wait on tooling
      maturity. The 2024 REPORT Act amended this section since it was last
      checked here: the preservation window for reported material extended
      from 90 days to **one year**, and the reportable-category list widened
      to include certain trafficking/enticement offenses, not just CSAM
      itself — the retention/deletion tooling this list requires elsewhere
      (P1) needs a carve-out for whatever this process ends up preserving.
- [ ] **Get a *written, district-facing* no-training-on-data guarantee on
      record** — resolves `GAPS.md` line 35. **Technical half confirmed
      live 2026-07-21** (`SAFETY.md` §3): traced `AI_GATEWAY_URL` →
      `litellm` → `open-webui` → `OLLAMA_BASE_URL` end to end: every hop
      stays inside this project's own containers, on an open-weight model,
      no `.env` override pointing any of it at a hosted vendor today. What's
      still open isn't "which vendor" (there isn't one) — it's that "true in
      the compose file" and "stated in the district agreement" are
      different claims, and only the first one exists. Still blocking until
      the second one does; also needs re-checking if `OPENWEBUI_BASE_URL`/
      `OLLAMA_BASE_URL` ever get pointed at a hosted backend.
- [ ] **Encryption-in-transit/at-rest audit** — confirm this is actually
      true in the current deployment, not assumed true because it's the
      obvious default.

---

## P1 — Required before the pilot scales past a handful of students

- [ ] **Build the facilitator moderation queue** — both the
      `instructor-dashboard` projection and the page on it, neither of
      which actually exists (`GAPS.md` line 63, corrected there and in
      `SAFETY.md` §5 after this repo previously claimed the backend was
      already built). A larger task than "add a page," but not a
      re-architecture: the exact event-consumer-writes-a-projection
      pattern that already builds `player-profile`/`team-profile` in
      `workers.py` applies directly. Photo/screenshot visibility flips
      from "live on submit" to "pending facilitator approval." Chat
      moderation specifically is the natural first consumer of the
      `evoke-events`-routed chat events described below.
- [ ] **Build a working "report" action** on every chat surface (B1llbot,
      Minecraft chat, team chat) — currently doesn't exist anywhere in the
      product.
- [ ] **Name the actual self-harm/crisis escalation contact and response
      window for the Colorado pilot district** — `SAFETY.md` §6 correctly
      says this can't be decided by EVOKE alone; it needs the district's
      answer, not a placeholder.
- [ ] `[COPPA]` **Pick and document an actual chat-retention window** (a number of
      days) — currently unspecified. Needs to balance the
      data-minimization requirement against the "long enough to support an
      abuse investigation" requirement; can't stay silent on the number.
      **This has a real regulatory deadline now, not just a best practice:**
      the FTC's amended COPPA Rule (effective June 23, 2025; compliance
      required by April 22, 2026 — already past) prohibits retaining
      children's data longer than reasonably necessary for the purpose
      collected, and requires it be documented as a written policy, not
      left implicit. `GUARDRAILS_PLAN.md`'s architecture for this changed
      during reconciliation: chat events route through the same Redpanda
      topics and MinIO storage every other event in this app already uses
      (`ChatMessageLogged` → `evoke-events` → a new worker → MinIO), not a
      second logging system inside LiteLLM's own optional Postgres mode —
      not built yet, but the pattern is proven six times over already in
      `workers.py`.
- [ ] `[COPPA]` **Annual data-security risk assessment** — also new in the
      amended COPPA Rule (see above): operators must implement and document
      written security programs, including annual risk assessments,
      before April 22, 2026 (already past). No such assessment exists in
      this repo today.
- [ ] **Harden the AI gateway past its Phase 0/1 dev defaults before real
      student traffic.** `evoke-infra/litellm` is live and doing real
      PII-masking/content-filter work today, but three things are still
      dev-shaped: `LITELLM_MASTER_KEY`/`AI_GATEWAY_KEY` default to
      `sk-devsecret123` in every compose file that references them, Presidio
      PII detection is the only privacy layer (`GUARDRAILS_PLAN.md` Phase 2's
      Llama Guard 3 content-safety model isn't deployed), and there's no
      Postgres-backed log yet (previous item). None of these block the pilot
      the way the P0 items above do, but "the guardrails exist" and "the
      guardrails are pilot-ready" are different claims.
- [ ] **Strip EXIF/location metadata** from uploaded photos before storage.
- [ ] `[COPPA]` `[CO-SDTSA]` **Build the single-learner full-data-footprint
      deletion path** (Postgres + object storage + logs + chat history,
      deletable as one action) — the shared technical requirement both
      COPPA's and the Colorado SDTSA's deletion rights depend on.
- [ ] `[FERPA]` **Build an access/disclosure audit log for education
      records** — new this pass. FERPA's school-official exception is
      conditioned on the district retaining real oversight of its data;
      today there's no record of who (which EVOKE staff, which system)
      accessed a given student's records, which is the concrete thing a
      district would need in order to actually exercise that oversight,
      not just be promised it exists.
- [ ] `[CO-CPA]` **Make an explicit, documented decision on Colorado
      Privacy Act opt-in requirements** for the 13–17 population — SB 24-041's minors
      amendment took effect October 1, 2025 (already in force, checked
      live against current statute status, not carried over from an older
      read). "EVOKE does none of targeted advertising, sale, or profiling"
      resolves three of the five triggers, but the amendment's opt-in list
      is wider than that: it also covers extended data retention **and,
      the one worth a real second look, "design features that
      significantly increase, sustain, or extend a minor's use of the
      service."** This app's streaks, XP, badges, and the Team Wheel are
      gamification mechanics built specifically to sustain engagement —
      whether that phrase reaches them is a real legal question, not a
      rhetorical one, and hasn't been asked of counsel yet. Enforcement
      grace period (60-day cure notice before AG/DA action) runs through
      December 31, 2026.
- [ ] `[CO-BREACH]` **Write the Colorado 30-day breach-notification
      runbook** — named responsible party, and the CO Attorney General
      notification trigger at 500+ affected Colorado residents
      (C.R.S. § 6-1-716).
- [ ] `[CIPA]` **Fix the Minecraft server's exposure — confirmed, not
      hypothetical.** New link drawn this pass: this is a CIPA item, not
      just a general security one — a district's own CIPA certification
      requires an internet safety policy covering "the safety and security
      of minors when using electronic mail, chat rooms, and other forms of
      direct electronic communication," and an open, unwhitelisted server
      with no chat-disable mechanism is in direct tension with a district
      being able to truthfully certify that. `WHITELIST.md` checked:
      `white-list=false` and `online-mode=false` are still today's
      defaults, and the historical server logs show real consequences, not
      a theoretical risk — a self-identifying scanner bot, a confirmed
      uninvited human who joined and left within 25 seconds, and ~45 other
      single-join names with IPs scattered across the open internet.
      `WHITELIST.md` §3 names the four required changes (`online-mode=true`,
      `white-list=true`, `enforce-whitelist=true`, and a chat-disable
      mechanism vanilla doesn't provide by default) — none are made yet.
- [ ] **Review the deployment against Microsoft's Minecraft Usage
      Guidelines** — the Geyser/Floodgate bridge means this server sits
      outside Xbox Live's own moderation scope entirely; confirm the
      deployment model itself stays within Microsoft's terms as it scales.
- [ ] `[CO-AI]` **New this pass, not previously in this list: assess
      Colorado's automated-decision-making law (SB 26-189) against the AI
      COACH WORKER's epic-tier award grant.** Colorado repealed and
      replaced its
      original AI Act (SB 24-205) with SB 26-189, signed May 14, 2026,
      effective **January 1, 2027** — not yet in force, but worth reading
      now rather than at the deadline. It requires disclosure/technical
      documentation from anyone deploying "covered ADMT" that materially
      influences a "consequential decision," and the statute's own
      education examples are admissions, financial aid, enrollment, and
      **automated grading**. B1llBot's system prompt explicitly refuses to
      grade or evaluate work (`GAME_DESIGN.md` §10) — a real, defensible
      argument this stays out of scope — but the AI COACH WORKER's
      automated epic-tier award determination is exactly the kind of
      automated, no-human-in-the-loop output the statute is aimed at, even
      if "which reward tier a game grants" isn't obviously the same weight
      class as "grading." Not resolved here; needs an actual reading by
      counsel before January 1, 2027, not an assumption either way.

---

## P2 — Governance and ongoing process, never "done"

- [ ] **Name an annual-review owner** for `SAFETY.md`, the compliance
      checklist artifact, and this list — a real person, not "someone
      eventually."
- [ ] **Add a ship gate**: any new feature touching chat, photo upload, or
      learner-identifying data gets checked against `SAFETY.md` + the
      checklist artifact before ship, not audited after the fact.
- [ ] **Mandatory-reporter awareness training** for facilitators and EVOKE
      staff who could plausibly receive a disclosure that triggers a
      reporting duty — can't rely on AI catching everything.
- [ ] **WCAG 2.1 AA pass + screen-reader testing** on the newest, least
      tested surfaces (Companion Mode, the Minecraft-quest reporting flow).
- [ ] **Track California's Age-Appropriate Design Code Act (AB 2273)
      litigation status** — low relevance to the Colorado pilot today, but
      worth monitoring before any expansion to California.
- [ ] `[CIPA]` **Write CIPA support documentation for districts** — a short
      description of EVOKE's own monitoring/moderation posture that a
      district can hand to its own E-rate compliance reviewer on request.

---

## Sourcing

- `SAFETY.md` — code of conduct, COPPA/FERPA posture, AI-reject/human-approve
  moderation model, the queue, escalation SLA.
- `GUARDRAILS_PLAN.md` — the AI gateway build spec (LiteLLM + Presidio +
  content filter) and its stakeholder/liability/technical reasoning; Phase
  0/1 is live as of this list's last edit, Phase 2+ is not.
- `WHITELIST.md` — confirmed evidence the Minecraft server has been reached
  by non-project entities (scanner bot, at least one uninvited stranger),
  the six team members verified and cleared to whitelist, and the four
  server-config changes required to close the exposure.
- Published artifact: *EVOKE — Minor Safety & Legal Requirements Checklist*
  — full US legal scope (COPPA, FERPA/state law, CIPA, CSAM reporting,
  Minecraft/platform safety, chat safety, content submission, data
  security, accessibility, governance).
- This thread's Colorado-specific findings: Student Data Transparency and
  Security Act, Colorado Privacy Act, Colorado breach-notification law.
- Student Data Privacy Consortium / NDPA registry (`privacy.a4l.org`),
  Colorado Department of Education's AI page and the Colorado Roadmap for AI
  in K-12 Education, and Common Sense Media's Youth AI Safety Institute risk
  assessments (Claude, Gemini K-12, ChatGPT) — confirmed live 2026-07-18: no
  state/federal AI model whitelist exists; the NDPA+exhibit path is the real
  mechanism; Claude's crisis guardrail is known to reset across conversations,
  untested for B1llbot.
- `GAPS.md` lines 31, 33, 35, 37, 56, 101, 116, 121, 123, 146 — the
  originally-flagged, previously-undecided items this list resolves into
  concrete actions.
- **Live regulation lookup, 2026-07-18** (not re-derived from this repo's
  own prior notes) — confirmed via current sources, not training-data
  recall: the FTC's amended COPPA Rule (effective June 23, 2025; compliance
  deadline April 22, 2026, already passed as of this check — retention
  limits and annual security risk assessments are now real requirements,
  not just good practice); the REPORT Act's 2024 amendment to 18 U.S.C.
  § 2258A (90-day → one-year preservation window); Colorado's SB 24-041
  minors amendment to the Colorado Privacy Act, effective October 1, 2025
  (opt-in required for "design features that significantly increase,
  sustain, or extend a minor's use," not just ads/sale/profiling); and
  Colorado's SB 26-189, which repealed and replaced the original AI Act
  (SB 24-205), signed May 14, 2026, effective January 1, 2027 — not
  previously tracked anywhere in this repo.
