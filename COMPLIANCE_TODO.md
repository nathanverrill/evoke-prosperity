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

---

## P0 — Blocking before any real student data is collected

- [ ] **Sign a Colorado Student Data Transparency and Security Act
      agreement with the pilot district** (C.R.S. §§ 22-16-101–113) — almost
      certainly the multi-state Student Data Privacy Consortium (NDPA)
      template plus Colorado's exhibit, since that's what CO districts
      generally expect rather than a custom contract.
- [ ] **Decide and document the COPPA consent path per cohort** — for this
      pilot specifically, that's the FTC school-official exception via the
      same district agreement above, not verifiable parental consent
      collected directly. Put this in writing; don't leave it implicit.
- [ ] **Wire CSAM hash-matching (e.g. PhotoDNA) into every photo-upload
      path** before storage. Blocking because photo upload is already a
      shipped feature today — this isn't a future-feature gate, it's an
      existing gap on a live upload surface.
- [ ] **Write the NCMEC CyberTipline reporting process and name an owner**
      — needs to exist on paper before automated detection is even fully
      tuned; the legal duty (18 U.S.C. § 2258A) doesn't wait on tooling
      maturity.
- [ ] **Confirm the actual LLM backend behind `OPENWEBUI_BASE_URL` and get
      a written no-training-on-data guarantee**, or switch to a
      self-hosted model — resolves `GAPS.md` line 35. Blocking because
      B1llbot chat and AI-Coach review both already send real student text
      to whatever that endpoint resolves to, today.
- [ ] **Encryption-in-transit/at-rest audit** — confirm this is actually
      true in the current deployment, not assumed true because it's the
      obvious default.

---

## P1 — Required before the pilot scales past a handful of students

- [ ] **Build the facilitator moderation queue UI** on the existing but
      page-less `instructor-dashboard` projection (`GAPS.md` line 56,
      `SAFETY.md` §5). Photo/screenshot visibility flips from "live on
      submit" to "pending facilitator approval."
- [ ] **Build a working "report" action** on every chat surface (B1llbot,
      Minecraft chat, team chat) — currently doesn't exist anywhere in the
      product.
- [ ] **Name the actual self-harm/crisis escalation contact and response
      window for the Colorado pilot district** — `SAFETY.md` §6 correctly
      says this can't be decided by EVOKE alone; it needs the district's
      answer, not a placeholder.
- [ ] **Pick and document an actual chat-retention window** (a number of
      days) — currently unspecified. Needs to balance the
      data-minimization requirement against the "long enough to support an
      abuse investigation" requirement; can't stay silent on the number.
- [ ] **Strip EXIF/location metadata** from uploaded photos before storage.
- [ ] **Build the single-learner full-data-footprint deletion path**
      (Postgres + object storage + logs + chat history, deletable as one
      action) — the shared technical requirement both COPPA's and the
      Colorado SDTSA's deletion rights depend on.
- [ ] **Make an explicit, documented decision on Colorado Privacy Act
      opt-in requirements** for the 13–17 population — likely resolved by
      "EVOKE does none of targeted advertising, sale, or profiling," but
      that has to be a written decision, not a silent default that happens
      to be true today.
- [ ] **Write the Colorado 30-day breach-notification runbook** — named
      responsible party, and the CO Attorney General notification trigger
      at 500+ affected Colorado residents (C.R.S. § 6-1-716).
- [ ] **Verify the Minecraft server isn't publicly discoverable/joinable**
      outside the enrolled cohort — a "should already be true" item that
      needs an actual check, not an assumption.
- [ ] **Review the deployment against Microsoft's Minecraft Usage
      Guidelines** — the Geyser/Floodgate bridge means this server sits
      outside Xbox Live's own moderation scope entirely; confirm the
      deployment model itself stays within Microsoft's terms as it scales.

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
- [ ] **Write CIPA support documentation for districts** — a short
      description of EVOKE's own monitoring/moderation posture that a
      district can hand to its own E-rate compliance reviewer on request.

---

## Sourcing

- `SAFETY.md` — code of conduct, COPPA/FERPA posture, AI-reject/human-approve
  moderation model, the queue, escalation SLA.
- Published artifact: *EVOKE — Minor Safety & Legal Requirements Checklist*
  — full US legal scope (COPPA, FERPA/state law, CIPA, CSAM reporting,
  Minecraft/platform safety, chat safety, content submission, data
  security, accessibility, governance).
- This thread's Colorado-specific findings: Student Data Transparency and
  Security Act, Colorado Privacy Act, Colorado breach-notification law.
- `GAPS.md` lines 31, 33, 35, 37, 56, 101, 116, 121, 123, 146 — the
  originally-flagged, previously-undecided items this list resolves into
  concrete actions.
