# HOSTING_COST_MODEL.md — per-cohort AWS sizing and cost framework

Companion to `ARCHITECTURE.md` (the "one box per organization" deployment model) and `GAPS.md`'s Business & adoption section (the AMI-per-cohort decision this framework sizes). This doc answers two questions: **what should one cohort's instance look like, and what does it cost** — plus an honest statement of how much of "spin up a cohort" is actually automated today (short answer: none of it yet).

**Pricing basis:** AWS us-east-1 on-demand rates, checked July 2026. Re-verify before using these numbers in a contract or pitch deck — AWS pricing drifts, and none of the automation below has been built yet, so nothing here has been validated against a real running AWS bill.

---

## 1. Current state: how much of this is automated?

**None of it.** This is a sizing/cost *framework* for a decision that's been made (`GAPS.md`: "one AWS instance per cohort, spun up from a golden AMI, operated by EVOKE") but not yet built. Concretely, none of these exist today:

- A baked golden AMI
- A script that launches a cohort instance
- Per-instance secret generation (cloud-init or otherwise)
- DNS/TLS automation
- A chosen root domain (nothing's registered yet — this blocks everything downstream, since Brightspace/LTI registration needs live DNS+TLS before a district admin can register launch/JWKS/redirect URLs)

Everything in this repo has only ever been run as local Docker Compose (`quick-start.sh`), never on a real AWS instance. Standing up a real cohort today means a person manually doing what `quick-start.sh` does, by hand, on a fresh EC2 box: launch it, install Docker, clone the repo, hand-write real secrets into `.env`, run `docker compose up -d` in both `evoke-infra/` and `evoke/`, point DNS at the instance's IP, get a TLS cert. That's real, working, and exactly what's been tested end-to-end all session — just not yet automated or run on AWS itself.

---

## 2. Sizing framework

Per `ARCHITECTURE.md`'s "one box per organization" principle, a single instance runs the entire stack for one cohort: Postgres, Redpanda, OpenSearch, MinIO, the `evoke` web app + background workers, the Minecraft reward bridge, OpenWebUI, and — for the Prosperity campaign specifically — a Minecraft Java server (Fabric + Geyser/Floodgate for Bedrock clients, currently configured for up to 40 players). `brightspace-sim` is dev-only and is not part of a real deployment (real districts use their actual Brightspace instance).

**Two things dominate sizing:**

1. **Minecraft is the heavy part, not the web app.** The existing config budgets it a 4GB JVM heap. Everything else — Postgres, Redpanda (single broker), OpenSearch (single node), MinIO, the web app, OpenWebUI (without local inference), the bridge — is a modest classroom-scale workload (dozens of users, low event volume) that fits comfortably in another 5–8GB combined.
2. **The AI backend is a real, open cost lever** (`GAPS.md` flags this directly: "minors' work may reach a third-party LLM vendor," still an unresolved decision). Two paths:
   - **Self-hosted inference** (Ollama or similar behind OpenWebUI) needs a GPU instance running continuously for what's actually bursty, low-volume usage (a few dozen students, async pacing over weeks) — expensive relative to the load.
   - **A hosted OpenAI-compatible API** behind OpenWebUI needs no GPU at all, just API spend that scales with actual usage.

   **Recommendation: the hosted-API path.** It's cheaper for this usage pattern and avoids needing to manage model weights per instance — but the vendor's data-processing/no-training terms need to be settled as part of picking the vendor, not treated as a separate problem later.

   **Not a contradiction of the above:** `evoke-infra/docker-compose.yml` now includes a containerized `ollama` service as the *local-dev/demo* default, so a fresh clone works without a native Ollama install. That's a developer-experience choice, sized for one laptop — it doesn't change the recommendation for real cohort instances, which is still the hosted-API path above (self-hosted CPU inference for a real classroom's actual concurrency needs a real GPU to stay responsive, which is the expensive path this section is steering away from).

**Recommended instance: `m5.xlarge`** (4 vCPU / 16GB RAM, non-burstable) as the default when Minecraft is in play. Deliberately *not* the cheaper `t3.xlarge`: Minecraft's tick loop is sustained background load whenever anyone's connected, and a burstable (T-family) instance can exhaust its CPU credit balance mid-class, which is exactly the wrong moment for the box to throttle.

**If a district opts out of Minecraft** (it's optional by design — see `GAPS.md`'s "Non-Minecraft students" gap), a much smaller box covers just the web app: **`t3.large`** (2 vCPU / 8GB) is fine, since there's no sustained background tick load to protect against and the workload is genuinely bursty (page loads, occasional AI calls).

**Storage:** a 100GB gp3 EBS volume covers the Minecraft world, Postgres, MinIO evidence files (images/PDFs), and OpenSearch indices with real headroom for a single classroom-scale cohort over a semester. Snapshot regularly (ties into `GAPS.md`'s "no backup story" gap, still open).

**Skip a NAT Gateway.** At this instance size, a NAT Gateway (~$32/mo base + per-GB data processing) would roughly double the whole budget for no real benefit. Put the instance in a public subnet with a tight security group instead — nothing about this deployment needs outbound-only routing.

---

## 3. Monthly cost per cohort

| Item | With Minecraft (`m5.xlarge`) | Web-only, no Minecraft (`t3.large`) |
|---|---|---|
| EC2 compute, on-demand, 24/7 | $140 | $61 |
| EC2 with a 1-yr Compute Savings Plan (~28% off on-demand) | ~$100 | ~$44 |
| EBS gp3, 100GB + snapshots | $10–12 | $5 |
| Data transfer out | $5–10 | $3–5 |
| Route53 (shared apex zone, amortized per cohort) | ~$1 | ~$1 |
| Hosted LLM API (scales with B1llbot chat + AI-review volume) | $10–50 | $10–50 |
| **Total, on-demand** | **~$165–215/mo** | **~$80–120/mo** |
| **Total, with a Savings Plan** | **~$125–175/mo** | **~$65–105/mo** |

**Run it 24/7 during the cohort's active enrollment window, not just during class hours.** The product deliberately wants students visiting between class periods (the activity feed and check-in mechanic exist specifically for this — see `GAME_DESIGN.md`/the activity-feed build). Shutting the instance down outside school hours would undercut a feature that's already shipped, for a saving that's small relative to the total (compute is roughly half the bill; the rest — storage, LLM API, DNS — doesn't scale down with instance uptime anyway).

**Scaling to N cohorts:** because there's no shared backend by design (isolation was the whole point of the AMI-per-cohort decision — see `GAPS.md`), cost is close to linear: **N cohorts ≈ N × the per-cohort number above**, plus small fixed fleet-wide costs (the apex Route53 hosted zone, ~$0.50/mo; AMI storage in S3, a few dollars/mo; and, once built, a fleet monitoring aggregator). There is no volume discount from shared infrastructure to plan around — each cohort is a genuinely separate bill.

---

## 4. What it takes to actually get here (phased)

- **Phase 0 — today.** Fully manual, as described in §1. Works, costs a few hours of skilled engineering time per cohort, has never been run on real AWS.
- **Phase 1 — minimum viable automation** (each item already scoped as `[build]` in `GAPS.md`'s Business & adoption section, none built yet):
  1. **Pick the root domain.** Blocks everything else — LTI/Brightspace registration needs live DNS+TLS before a district admin can register launch/JWKS/redirect URLs, so this has to be step one, not an afterthought.
  2. **Bake a golden AMI** — Docker + the repo pinned to a release tag. No secrets baked in.
  3. **A cloud-init first-boot script** that generates unique per-instance secrets (RCON password, DB password, MinIO keys, JWT signing key) before anything starts — without this, every instance cloned from the same AMI ships identical secrets and the per-cohort isolation story is cosmetic.
  4. **A basic provisioning script** — doesn't need to be real IaC on day one, even a plain AWS CLI/SDK script is enough — that launches the instance from the AMI at the size chosen above, tags it with the cohort slug, and writes its two Route53 records (`{slug}.app.<root>`, `{slug}.mc.<root>`).
  5. **LTI credential exchange with the district stays a manual step regardless** — needs a human on both sides, no amount of automation removes that.
- **Phase 2 — needed once running more than 1–2 cohorts concurrently** (also already flagged in `GAPS.md`, not build-blocking for a single pilot): fleet-wide monitoring aggregation (nothing today aggregates health across N running instances into one view), a patch/version rollout mechanism (a golden AMI is good for isolation, bad for pushing a fix to N already-running instances without one), and an offboarding runbook (a defined snapshot-and-terminate or hard-delete path for end-of-contract/FERPA deletion requests — `SAFETY.md` §3 and `COMPLIANCE_TODO.md`'s P1 list now name the specific requirement this runbook has to satisfy: a named learner's full data footprint, enumerable and deletable as one action).

---

## 5. Sources for the pricing in §3

- [m5.xlarge pricing — Economize Cloud](https://www.economize.cloud/resources/aws/pricing/ec2/m5.xlarge/) — $140.16/mo on-demand, us-east-1 (≈$0.192/hr)
- [t3.xlarge pricing — Economize Cloud](https://www.economize.cloud/resources/aws/pricing/ec2/t3.xlarge/) — $121.47/mo on-demand, us-east-1 (≈$0.1664/hr)
- [t3.large pricing — Economize Cloud](https://www.economize.cloud/resources/aws/pricing/ec2/t3.large/) — $60.74/mo on-demand, us-east-1 (≈$0.0832/hr)
- [Amazon EBS pricing](https://aws.amazon.com/ebs/pricing/) — gp3: $0.08/GB-month, us-east-1
