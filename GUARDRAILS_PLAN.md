# GUARDRAILS_PLAN.md

## AI guardrails: stakeholder, liability, and technical plan

**Status: proposed, not yet built.** Every AI call in this app today (B1llBot
chat, the daily Field Report's word of wisdom, mission-evidence review) goes
straight to OpenWebUI with no intermediary — no PII check, no content-safety
check, no centralized log, no rate limit. This plan is the build spec for
closing that gap: a self-hosted gateway sitting in front of OpenWebUI, using
real open-source guardrail tooling rather than a bespoke classifier, and the
reasoning — who needs this, what it actually reduces liability-wise, and how
it fits the codebase as it exists today, not a theoretical rewrite.

**Not legal advice**, same caveat as `SAFETY.md` and `COMPLIANCE_TODO.md`,
which this plan is downstream of — those two documents already establish
the policy this plan makes technically real. Have actual counsel review
before treating any part of this as a compliance sign-off.

---

## I. Stakeholder perspective

Different people need different things from this system, and a plan that
only satisfies engineering isn't actually done.

| Stakeholder | What they actually need | What this plan gives them |
|---|---|---|
| **Students** | Not to be exposed to something harmful in a conversation they didn't choose to have, and not to have their own private information exposed by mistake | Input and output both checked before either the model or the student sees the other side |
| **Parents/guardians** | Confidence that an AI character talking to their kid has real limits, and that this was thought through, not bolted on | A written, inspectable policy (`SAFETY.md` §2–4) with a technical system that actually enforces it, not just a system prompt asking nicely |
| **Teachers/facilitators** | Not to be the safety net for something a machine should have caught first, but to still be the ones who decide anything that actually matters | The "AI may auto-reject, only a human can approve" split (§III below) — volume goes down, judgment calls still reach a person |
| **District administrators** | A real answer to "what happens if a student's chat says something concerning" before they'll sign anything | A named escalation shape (§III, §"what this doesn't resolve") — the technical half of the answer; the district still names the actual human and response-time commitment |
| **EVOKE leadership/product** | This not to become an unbounded cost center, and not to be the reason a pilot gets pulled | Rate limits and budget tracking come from the same gateway (resolves `GAPS.md`'s AI cost/rate-control gap as a side effect, not a separate project) |
| **Engineering** | Something that doesn't require every new AI call site to remember to implement safety by hand | One gateway, one place the rule lives — a new call site gets guardrails by construction, not by someone remembering |

**Communication path:** once built, this is also the technical backbone of
the CIPA support documentation `COMPLIANCE_TODO.md` already lists as a P2
item — "here's what we actually check, here's what we log, here's how fast
a flagged conversation reaches a human" is a real answer a district's
E-rate compliance reviewer can be handed, not a promise.

---

## II. Liability perspective

**The frameworks already in play** (full detail in `SAFETY.md` §3 and
`COMPLIANCE_TODO.md`) — COPPA, FERPA, the Colorado Student Data
Transparency and Security Act, CIPA, and NCMEC CyberTipline reporting
duties for CSAM. This plan doesn't re-derive any of that; it's the
technical mechanism that makes several of those commitments actually true
rather than aspirational.

**The core liability-management shape, and why it's shaped this way:**

> **AI may auto-reject. Only a human can make something visible.**
> (`SAFETY.md` §4, restated here because it's the design constraint
> everything in §III follows from)

An AI that silently *approves* harmful content is the liability scenario
that ends a pilot. An AI that *rejects* the obvious cases before a human
ever has to look is a defensible volume-reduction measure, not a
delegation of judgment. Every guardrail in this plan sits on the reject
side of that line — nothing here is designed to let anything through that
a human hasn't implicitly or explicitly cleared.

**Specific scenarios this plan exists to prevent:**

- A student types their phone number or address into B1llBot chat, and it
  gets logged, or worse, echoed back or surfaced somewhere another student
  or a projector could see it.
- A student expresses crisis/self-harm language and the system's only
  response is B1llBot's own in-character reply, with no path to a human
  faster than the ordinary review queue.
- A persona gets talked out of its own guardrails (prompt injection /
  jailbreak) and says something it was explicitly built not to.
- An AI review or wisdom-generation call, unrelated to safety on its face,
  still sends unfiltered student text to an external model with no record
  of what was sent or received.

**What this plan explicitly does not resolve** — named here so it isn't
mistaken for complete:

- **CSAM hash-matching on photo uploads** — a different problem (image,
  not text) with its own P0 item in `COMPLIANCE_TODO.md`. Out of scope
  here.
- **The actual consent agreements, DPAs, and breach-notification runbook**
  — paperwork, not code. `COMPLIANCE_TODO.md`'s P0/P1 lists own these.
- **Naming the actual crisis-escalation contact and response-time
  commitment** — `SAFETY.md` §6 is explicit this can't be decided by
  EVOKE alone; it's a per-district staffing commitment. This plan builds
  the pipe the escalation travels through, not the person on the other
  end.
- **The facilitator review queue** — `GAPS.md` line 63 territory. Neither
  the `instructor-dashboard` projection nor the page on it exists yet
  (corrected during this reconciliation; earlier drafts of this repo's
  docs claimed the backend was already built). This plan's "flagged,
  routed to a human" path assumes that surface exists; it's a real
  dependency, not a detail — see §III's Logging and retention section for
  the concrete plan to build it.

### Regulatory landscape — checked live, not carried over from memory

A few developments outside this repo's own prior notes, confirmed against
current sources rather than assumed current: the FTC's amended COPPA Rule
(compliance deadline April 22, 2026, already past) makes a documented
retention window and an annual security risk assessment real requirements,
not best practice; Colorado's SB 24-041 minors amendment to the Colorado
Privacy Act (effective October 1, 2025) requires opt-in consent for
"design features that significantly increase, sustain, or extend a
minor's use" — a real, unresolved question for this app's own streaks/XP/
badge mechanics, not just ad-tech; and Colorado repealed and replaced its
AI Act (SB 24-205 → SB 26-189, effective January 1, 2027), which regulates
automated decisions materially influencing "consequential decisions" —
education examples given include automated grading, which B1llBot's
system prompt explicitly refuses to do, but the AI COACH WORKER's
automated epic-tier award grant is a closer call worth a real legal read.
Full detail and citations: `COMPLIANCE_TODO.md`'s P1 list and its
"Sourcing" section.

---

## III. Technical perspective

### Current state

Four real call sites talk to OpenWebUI directly, no intermediary:

| Call site | File | Purpose |
|---|---|---|
| `billbot_chat()` | `evoke/main.py` | Real-time B1llBot conversation (Hub, Field Kit) |
| AI COACH WORKER | `evoke/workers.py` | Evidence-review insight generation + epic-tier award |
| FIELD REPORT WORKER | `evoke/workers.py` | Daily Field Report word-of-wisdom generation |
| `generate_lore_message()` | `evoke-minecraft-bridge/bridge.py` | Ambient in-Minecraft "did you know" lore lines |

All four use `OPENWEBUI_URL`/`OPENWEBUI_API_KEY` (or the `ai_client` OpenAI
SDK client in `evoke/clients.py`) and call the `billbot` custom model
directly. No PII check, no content-safety check, no shared log, no rate
limit — each call site is independently trusted to behave. The fourth is
worth calling out specifically: it's the one call site whose output lands
directly in a student's Minecraft chat window, unmoderated by a human,
which is exactly the surface guardrails matter most for.

### Proposed: a thin gateway, not a rewrite

**[LiteLLM Proxy](https://docs.litellm.ai/docs/proxy/guardrails/quick_start),
self-hosted, as one more container in `evoke-infra/docker-compose.yml`,**
sitting between the app and OpenWebUI. It's OpenAI-API-compatible, so every
existing call site changes by exactly one thing: the base URL each already
points at (`OPENWEBUI_URL` becomes the gateway's URL; the gateway is
configured to forward to OpenWebUI as its one real backend). No call site's
actual request/response handling code changes.

```
Today:      main.py / workers.py / bridge.py  ──▶  LiteLLM Proxy  ──▶  OpenWebUI
                                                     │
                                                     ├─ pre-call:  Presidio (PII) + Content Filter   [live]
                                                     ├─ post-call: same two, run on the reply         [live]
                                                     ├─ Llama Guard 3, pre- and post-call              [proposed]
                                                     └─ rate limit + budget per caller                 [proposed]

Also today:  main.py / workers.py / bridge.py  ──▶  publish_event("ChatMessageLogged")  ──▶  Redpanda
                                                     │
                                                     └─ CHAT ARCHIVE WORKER (workers.py)      [proposed]
                                                        ├─ full exchange → MinIO (history, playback)
                                                        └─ moderation-queue projection → OpenSearch
                                                           (the facilitator queue's real data source)
```

### The guardrail stack, and why each piece

All three real building blocks are open-source, self-hosted, documented
LiteLLM integrations — not a bespoke classifier built from scratch, and
not a commercial vendor a student's text has to leave the box to reach:

1. **[LiteLLM's built-in Content Filter](https://docs.litellm.ai/docs/proxy/guardrails/litellm_content_filter)**
   — regex/keyword-based, zero external dependencies, ships with LiteLLM
   itself. Cheapest possible first layer; catches the unambiguous cases
   (explicit slurs, obvious phone-number patterns) before anything else
   even runs. **Deliberately does not cover self-harm/child-safety
   categories**, even though the filter ships them — that's item 4's job
   (crisis/self-harm needs the escalation-routing behavior, not a block),
   and shipping Phase 1 with `harmful_self_harm` on this filter's BLOCK
   list — before item 4 existed to replace it — produced exactly the wrong
   behavior in testing: it silenced B1llbot's crisis-redirect instead of
   escalating it. Fixed; see `SAFETY.md` §6 and
   `evoke-infra/litellm/config.yaml`'s comment on `content-filter-pre` for
   the full incident. Until item 4 is actually built, self-harm/child-safety
   language reaches B1llbot exactly as it did before this gateway existed —
   a known gap, not a silent one.
2. **[Presidio](https://docs.litellm.ai/docs/tutorials/presidio_pii_masking)**
   (Microsoft, open source) — real PII detection/masking, configurable to
   block or redact. Directly implements `SAFETY.md` §2's "keep your real
   name, address, phone number to yourself." Self-hostable.
3. **[Llama Guard 3](https://ollama.com/library/llama-guard3)** (Meta,
   open-weight) — a real content-safety classification model for violence,
   hate speech, self-harm, and sexual-content categories. Runs on the
   **same Ollama container this project already operates** — no new
   vendor, no new infrastructure category, just one more model pulled
   into an existing service.
4. **[Custom Guardrail](https://docs.litellm.ai/docs/proxy/guardrails/custom_guardrail)**
   (LiteLLM's documented extension point) — for the one EVOKE-specific
   rule none of the above cover: routing crisis/self-harm language to the
   fast escalation path (`SAFETY.md` §6) instead of the ordinary review
   queue. This is a small, focused piece of code, not a second classifier
   built from nothing — it reuses Llama Guard's own classification output
   and adds the routing decision on top.

**Deliberately not in the first version:** the catalog of commercial
guardrail providers (Lakera, HiddenLayer, Javelin, Qualifire, EnkryptAI,
Pillar Security, IBM FMS Guardrails, Guardrails AI) are real LiteLLM
integrations, but every one of them means student text leaves the box for
a third party. `SAFETY.md` §3 already requires a written no-training-on-
data guarantee before that's acceptable for any hosted vendor — none of
that paperwork exists today, so self-hosted stays the default until it
does, not as a permanent architectural rule but as the current honest
state.

### Pre-call and post-call, concretely

- **Pre-call** (before the student's message reaches the model):
  Presidio + content filter run first (fast, cheap, no model needed for
  the regex/PII layer); Llama Guard classifies for the harm categories.
  Clearly disallowed → rejected immediately, with a plain, specific reason
  ("this couldn't be sent — it looks like it includes a phone number"),
  never silently dropped, matching `SAFETY.md` §4's rejection UX. Crisis
  language → the custom guardrail's escalation routing fires *in addition
  to* whatever the model does, not instead of it — B1llBot's own
  in-conversation crisis guardrail (`GAME_DESIGN.md` §10) stays the
  immediate response; the escalation is the parallel path to a human.
- **Post-call** (before the model's reply reaches the student): the same
  Llama Guard classification runs on the output. This is the backstop for
  the case pre-call can't catch — a clean input that still produces an
  unsafe reply, whether from a jailbreak attempt or a model mistake.

### Logging and retention — revised: the app's own event bus, not a second logging system

The original version of this section proposed logging every
request/response inside LiteLLM's own optional Postgres-backed mode. On
reconsideration, that's the wrong home for it: this app already has a
durable, replayable, audited event log for everything else that happens
in it — Redpanda topics (`evoke-events`/`minecraft-events`) consumed by
`workers.py`, with results written to OpenSearch projections and MinIO
object storage. Building a *second*, parallel logging system inside
LiteLLM duplicates infrastructure this repo already runs and already
knows how to operate, for no real benefit.

**Revised plan:** every real AI call site publishes a `ChatMessageLogged`
event (matching the existing `publish_event()`/`topic_for_event()`
pattern already used for `EvidenceSubmitted`, `ReflectionFiled`,
`WisdomReady`, etc.) once a request/response round-trip completes. A new
`workers.py` consumer — call it the **CHAT ARCHIVE WORKER**, the same
shape as every other numbered worker block in that file — does two
things per event, both following patterns already proven elsewhere in
this exact codebase:

1. Writes the full exchange to MinIO (`s3_client.put_object(...)`,
   the same client `AI COACH WORKER` already uses to read evidence) —
   durable storage, full history, real playback, not a log line that
   scrolls away.
2. Indexes it into a new `moderation-queue` OpenSearch projection
   (`os_client.index(...)`, the same pattern that already builds
   `player-profile`/`team-profile`/`activity-feed`) — which is also the
   real data source the facilitator moderation queue (§IV of the
   companion artifact) needs to exist before it can show a human
   anything.

This is real, unstarted work — not done by writing this paragraph — but
it is *not* a re-architecture. Every piece of the pattern (an event type,
a `publish_event()` call, a `workers.py` consumer block, an S3 write, an
OpenSearch projection write) already exists at least once in this
codebase today; this is applying a proven pattern to a new event type,
not inventing a new one. It also directly resolves the "B1llBot can't
notice an escalating distress pattern across a sitting" gap (`SAFETY.md`
§6): once messages are events, "the last N messages for this user" is a
projection query, not a missing architecture.

This is also what `COMPLIANCE_TODO.md`'s P1 item ("pick and document an
actual chat-retention window") actually needs to exist before that
policy can be anything but a number on paper — and, per that list's
newly-added COPPA finding, the FTC's amended Rule makes that retention
window a real compliance deadline, not just good practice.

**Found during verification, worth remembering:** `LITELLM_LOG=DEBUG`
prints the *pre-mask* request text to container stdout — including the
raw PII Presidio is about to redact. Fine as a one-off diagnostic (used to
confirm the guardrails were actually firing while building this), but it
must never run as the container's normal log level — it would defeat the
PII guardrail's own purpose by leaking the same data into Docker's log
driver instead.

### Rate limiting and cost control

LiteLLM's per-key rate limits and budget tracking resolve `GAPS.md`'s open
"AI cost/rate control" gap as a direct consequence of adopting the gateway,
not a separate build: a stuck retry loop or a runaway chat session hits a
real ceiling instead of an unbounded bill.

---

## Phased rollout

Not everything lands at once — each phase is independently shippable and
de-risks the one after it.

| Phase | What ships | Why this order |
|---|---|---|
| **0. Pass-through** ✅ | LiteLLM proxy stood up, zero guardrails active, every call site repointed at it | Proves the plumbing (routing, latency, container health) with no behavior change — if something breaks, it's the gateway, not a guardrail |
| **1. Cheap wins** ✅ | LiteLLM's built-in content filter + Presidio | Fast, no model inference needed, closes the PII gap immediately |
| **2. Content safety** | Llama Guard 3, pre- and post-call | Needs a model pull + real latency/perf validation against B1llBot's existing response-time expectations |
| **3. Escalation routing** | The custom guardrail for crisis-language routing | Depends on the facilitator queue existing somewhere to route *to* — and, corrected during this reconciliation, that means the `moderation-queue` projection and the `CHAT ARCHIVE WORKER` that builds it, not just a missing page on an already-built backend |
| **4. Retention + tuning** | Formal retention window enforced against the log table; rate limits/budgets tuned from real usage | Needs real traffic data from phases 0–2 to set sane numbers, not guesses |

---

## Open decisions — need a human call, not an engineering default

- **Retention window length** — balances data-minimization against
  "long enough to support an abuse investigation" (`COMPLIANCE_TODO.md`
  P1). Not decidable by this plan.
- **Named crisis-escalation contact and response-time commitment**
  (`SAFETY.md` §6) — a per-district staffing decision.
- **Latency budget** — Llama Guard adds a real inference call on both the
  pre- and post-call path. How much added latency is acceptable before it
  degrades B1llBot's conversational feel needs a real answer, tested
  against actual hardware, not assumed.
- **Whether any commercial guardrail provider is ever acceptable**, and
  under what DPA terms — an open question this plan deliberately defers
  rather than answers by default.

---

## Sourcing

- `SAFETY.md` — code of conduct, COPPA/FERPA posture, the AI-reject/
  human-approve model, the facilitator queue design, escalation SLA shape.
- `COMPLIANCE_TODO.md` — the sequenced P0/P1/P2 list this plan's phases
  and open decisions are scoped against.
- `GAPS.md` — the AI cost/rate-control gap this plan resolves as a
  byproduct, and the facilitator-queue-UI dependency noted in §II/§III.
- [LiteLLM Guardrail Providers](https://docs.litellm.ai/docs/guardrail_providers),
  [Presidio PII Masking](https://docs.litellm.ai/docs/tutorials/presidio_pii_masking),
  [Llama Guard 3 on Ollama](https://ollama.com/library/llama-guard3),
  [LiteLLM Content Filter](https://docs.litellm.ai/docs/proxy/guardrails/litellm_content_filter),
  [Custom Guardrail](https://docs.litellm.ai/docs/proxy/guardrails/custom_guardrail) —
  verified live against current documentation, not assumed from training data.
