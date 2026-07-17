# EVOKE Hub mission-completion event + audit log — build prompt

Not built yet. This is the spec/prompt for the work, written so it can be
handed to an engineer or an AI coding agent as-is. Grounded in real code —
every file/function/line referenced below exists today; nothing here is
speculative except the EVOKE Hub API contract itself, which is new.

---

## The problem this solves

EVOKE Prosperity and EVOKE Hub carry two different kinds of risk, and they
need to stay cleanly separated:

- **EVOKE Prosperity's risk**: correctly detecting that a real learner
  genuinely completed a real mission, and reliably telling Hub that it
  happened. If we fire a false, duplicate, or missing completion event,
  that's our bug.
- **EVOKE Hub's risk**: whatever it does *after* receiving that event —
  blockchain transactions, financial disbursement, anything downstream.
  If Hub mishandles a valid event we sent it, that's Hub's bug, not ours.

The boundary between those two risks is the event itself. For that
boundary to hold up under audit ("prove you actually told Hub, and told
it the truth, and told it exactly once"), **we need our own durable,
tamper-evident record of every notification we ever sent** — independent
of Hub's own systems, independent of Kafka's retention policy, and
independent of whether the HTTP call to Hub even succeeded.

That's what this spec builds: a persisted, unique event ID, and a durable
audit log for every mission-completion notification sent to Hub.

---

## Where this hooks in

`evoke/main.py`'s `_complete_mission_for_user(user_id, mission_id, team_id)`
(currently starts at line 1188) is the single place `MissionCompleted`
fires. It's already idempotent — the function's own first move is an
already-completed guard (`SELECT 1 FROM awards WHERE ... tier = 'common'
AND source = 'submission'`, returns early if found) — so this is also the
one place a Hub notification can safely hook in without needing its own
separate "has this already happened" tracking for *whether the mission
completed*. (It still needs its own idempotency for *whether Hub was
already notified* — see below; those are two different questions.)

The exact insertion point is right after the existing:

```python
await publish_event("MissionCompleted", {
    "user_id": user_id,
    "mission_id": mission_id
})
```

(currently ~line 1265). Add the Hub notification + audit write immediately
after this, in the same function, same request lifecycle — not as a
separate consumer reacting to the Kafka event asynchronously. Reason:
firing it inline, in the same code path that just proved the completion is
real, keeps the audit trail's "why we believe this happened" tightly
coupled to the actual DB writes (the award insert, the reflection/evidence
rows) that prove it — a separate async consumer introduces a window where
the Kafka event exists but the audit log doesn't yet, or vice versa.

---

## 1. The event ID

Generate a UUID *deterministically*, not randomly, so a retried/duplicate
call to this function (already guarded above, but defense in depth) can't
mint two different IDs for the same real-world fact. Derive it from the
one thing that's true forever about this completion:

```python
hub_event_id = str(uuid.uuid5(uuid.NAMESPACE_OID, f"mission-completed:{user_id}:{mission_id}"))
```

`uuid5` is deterministic given the same inputs — calling this twice for
the same (user, mission) always produces the same ID. That ID is what
both the Hub API call and the MinIO audit object get keyed on. This
mirrors the existing pattern in the same function (`award_id =
str(uuid.uuid4())` a few lines above) — same shape, deliberately
deterministic instead of random because *this* ID's whole job is to be
re-derivable for dedup/audit lookups, not just unique.

---

## 2. The MinIO audit log — genuinely immutable, not just "durable-ish"

**Correction from the first draft of this spec**: writing a `status:
"pending"` object and then *overwriting* it with `delivered`/`failed`
(what this section originally said) is not actually tamper-evident — an
overwritable object is still a mutable record, no different in kind from
a Postgres row someone could `UPDATE`. Full governance-grade auditability
means the log is **append-only**: every state transition is its own new,
individually-locked object; nothing already written is ever modified,
only added to.

**Bucket setup (one-time, and it must happen at creation — Object Lock
cannot be retrofitted onto an existing MinIO/S3 bucket):**

```python
s3_client.create_bucket(Bucket="hub-events", ObjectLockEnabledForBucket=True)
```

Use **Object Lock in COMPLIANCE mode**, not GOVERNANCE mode, for every
object written here. This is a real, easy-to-miss naming collision worth
flagging explicitly: MinIO/S3's own **GOVERNANCE** retention mode still
lets a privileged credential delete or overwrite a locked object — it is
*not* what "just like governance [audit standards]" means, and using it
would quietly undermine the exact guarantee this spec exists to provide.
**COMPLIANCE mode** is the one where *no one* — not even the root
credential — can delete or modify an object before its retention period
expires. That's the actual tamper-evidence property. Retention period
itself is an open decision (align it to whatever EVOKE Hub's own
financial/compliance requirement turns out to be — 7 years is a common
default for financial records, but don't ship that number without
confirming it against Hub's actual requirement).

**Object layout — append-only per event, not one mutable file:**

```
hub-events/{hub_event_id}/00-detected.json     -- written the moment the AND-gate closes, before any Hub call
hub-events/{hub_event_id}/01-attempt.json      -- the exact outgoing request, written right before the HTTP call
hub-events/{hub_event_id}/02-result.json       -- the response/outcome of that attempt
hub-events/{hub_event_id}/03-attempt.json      -- only if attempt 1 failed and a retry fires
hub-events/{hub_event_id}/04-result.json
...
```

Each object is written once, locked immediately (`ObjectLockMode:
"COMPLIANCE"` + a `RetainUntilDate` on the `put_object` call), and never
touched again. "Current status" for a given `hub_event_id` is derived by
listing everything under its prefix and reading the latest numbered
object — a query, not a stored field — which is itself part of the audit
property: the full history is always there, not just the last write.

This ordering (write `00-detected` before attempting the Hub call at all)
is what survives a crash or timeout mid-call: even if the process dies
before `01-attempt` or `02-result` ever get written, there's still
immutable proof Prosperity had detected the completion and intended to
notify Hub, with a timestamp — enough to drive a manual reconciliation
even in the worst case.

**Honest gap in the current infra, not solved by this spec:** the
running MinIO (`evoke-infra-minio-1`, a single `chainguard/minio`
container, per `evoke-infra/docker-compose.yml`) is one node with no
erasure coding or replication — Object Lock makes records *tamper-evident*
(nobody can edit or delete them), it does not make them *durable against
losing the disk*. True governance-grade durability needs either a real
multi-node MinIO cluster or replication to a second location (a cloud
bucket, most likely) — that's infrastructure work beyond this spec's
scope, and should be a explicit decision (and cost line, see
`HOSTING_COST_MODEL.md`) before this is treated as a real financial audit
trail rather than a tamper-evident-but-single-copy one.

Example contents of each object in the sequence:

```json
// 00-detected.json
{
  "hub_event_id": "<uuid5, see above>",
  "event_type": "MissionCompleted",
  "user_id": "<uuid>",
  "mission_id": "<uuid>",
  "team_id": "<uuid>",
  "detected_at": "<ISO8601, when Prosperity's AND-gate closed>"
}

// 01-attempt.json
{
  "hub_event_id": "<uuid5>",
  "attempt": 1,
  "sent_at": "<ISO8601>",
  "hub_request": { "...": "exact payload sent to Hub" }
}

// 02-result.json
{
  "hub_event_id": "<uuid5>",
  "attempt": 1,
  "resolved_at": "<ISO8601>",
  "outcome": "delivered",
  "hub_response_status": 200,
  "hub_response": { "...": "exact response body from Hub" }
}
```

Use MinIO's normal `put_object` (via `s3_client`, same as evidence
uploads) with `ObjectLockMode="COMPLIANCE"` and a `RetainUntilDate` set on
every one of these calls.

**This MinIO log is the actual audit trail.** Kafka's `MissionCompleted`
event (already published, unchanged by this work) is for Prosperity's own
internal consumers (workers.py's badge/XP/profile logic) — it is *not*
durable enough to be Hub's audit record, since Redpanda topics here have
no configured long-term retention and were never meant to double as an
archive.

---

## 3. The EVOKE Hub API call

Contract is new — coordinate the exact shape with whoever owns Hub before
finalizing, but the request should carry at minimum:

```json
{
  "hub_event_id": "<the uuid5 from step 1>",
  "event_type": "mission.completed",
  "occurred_at": "<ISO8601>",
  "learner": { "evoke_user_id": "<uuid>" },
  "mission": { "evoke_mission_id": "<uuid>" },
  "team": { "evoke_team_id": "<uuid>" },
  "source": "evoke-prosperity"
}
```

Send `hub_event_id` as an idempotency key in whatever way Hub's API
expects (a header like `Idempotency-Key`, or a body field it dedupes on)
— Hub needs to be able to safely receive the same event twice (a Prosperity
retry after a timeout where the first attempt actually succeeded) without
double-processing a financial/blockchain action. This is the other half
of the risk boundary: Prosperity guarantees "at least once, with a stable
ID you can dedupe on"; Hub owns making dedup-on-that-ID actually safe on
its side.

Timeout + retry: a financial/blockchain-adjacent call should not be
fire-and-forget. A short timeout (5-10s) with a small number of retries
(e.g. 3, exponential backoff) is reasonable for the inline call, each one
its own numbered `NN-attempt`/`NN-result` pair per §2; if all retries
fail, the last `-result.json` in the sequence carries `"outcome":
"failed"` and the last error captured, and surface it somewhere a human
can see it (an admin
view, or at minimum a log line `logger.error(...)` — matches the existing
`except Exception as e: logger.error(f"Badge sync failed: {e}")` pattern
already used a few lines above for the Brightspace push, in the same
function). Do **not** let a Hub-call failure block or roll back the
learner's actual mission completion — the award/XP/badge/MissionCompleted
side of this function must succeed independently of whether Hub is
reachable, per the same "Minecraft/optional-integration stays at arm's
length" principle `ARCHITECTURE.md` already applies elsewhere in this
codebase.

---

## 4. What this spec deliberately does not cover

- Hub's own API authentication scheme, retry/dedup implementation, or
  anything about what Hub does with the event after receiving it — out of
  scope by design, that's Hub's side of the risk boundary.
- A backfill/replay tool for re-sending historical completions Hub never
  received (e.g. if this ships after real completions already happened).
  Worth a follow-up once this is live, not blocking the first version.
  The append-only log is exactly what such a tool would scan — any
  `hub_event_id` prefix whose latest object isn't a successful `-result`
  is a candidate for replay.
- Multi-node MinIO durability / cross-location replication (see the
  honest gap called out at the end of §2) — Object Lock solves
  tamper-evidence, not disk/node loss. A real decision + likely a real
  cost line, not something to silently assume is covered.
