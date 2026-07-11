# EVOKE Prosperity: Coding Roadmap Summary

**Status:** MVP complete ✅ → Brightspace simulator complete ✅ → Ready to code integration 🚀  
**Date:** July 2026  
**Duration:** 4 weeks for production-ready LMS integration  

---

## What Just Shipped

✅ **Brightspace API Simulator** (`brightspace-sim/brightspace_api.py`)
- Complete in-memory Brightspace implementation
- OAuth 2.0, Identity, Awards, Groups, Dropbox, Grading endpoints
- Production-ready test double for development

✅ **Brightspace Test Server** (`brightspace-sim/app.py`)
- FastAPI wrapper for simulator
- Teacher review UI for testing grading flow
- Ready for demo/testing before real integration

---

## Your Next 4 Weeks: Implementation Roadmap

### Week 1: Foundation (Parallel Work)
**Goal:** Get identity mapping working; add database tables

| Task | File | Effort | Status |
|------|------|--------|--------|
| Identity System | `evoke/main.py` | 2-3 hrs | TODO |
| Submission Tracking | `evoke-infra/init-db.sql` | 1 hr | TODO |
| Badge-Brightspace Mapping | `evoke-infra/init-db.sql` | 30 min | TODO |

**Definition of Done:** Can link Brightspace user ID ↔ EVOKE user ID ↔ Minecraft UUID

---

### Week 2-3: Production Integration
**Goal:** Real Brightspace connection replacing simulator

| Task | File | Effort | Status |
|------|------|--------|--------|
| BrightspaceLMS Adapter | `evoke/lms/brightspace_lms.py` | 4-5 hrs | TODO |
| Mission-Assignment Mapping | `evoke-infra/init-db.sql` | 30 min | TODO |
| Integration into main.py | `evoke/main.py` | 2 hrs | TODO |

**Definition of Done:** Evidence syncs to real Brightspace dropbox

---

### Week 3-4: Authentication & Grading
**Goal:** LTI login + teacher grading webhook

| Task | File | Effort | Status |
|------|------|--------|--------|
| LTI 1.3 Login Provider | `evoke/lti/brightspace_lti_provider.py` | 3-4 hrs | TODO |
| LTI Launch Endpoint | `evoke/main.py` | 1-2 hrs | TODO |
| Grading Webhook | `evoke/main.py` | 2-3 hrs | TODO |
| End-to-End Test | `tests/test_e2e_brightspace.py` | 2 hrs | TODO |

**Definition of Done:** Full LTI → submit → grade → reward flow works

---

## Key Documents

### 1. **BRIGHTSPACE_INTEGRATION_SPEC.md** (Architecture Blueprint)
**Read this if:** You want to understand the full design  
**Contains:**
- 5 components breakdown (identity, adapter, LTI, webhook, groups)
- Database schema additions
- OAuth 2.0 service account flow
- Integration test plan
- 4-week estimation + sequencing

**Time to read:** 15 minutes

---

### 2. **IMMEDIATE_NEXT_STEPS.md** (Day-by-Day Playbook)
**Read this if:** You're ready to start coding  
**Contains:**
- Exact SQL queries to run
- Code snippets for each endpoint
- Test commands (curl examples)
- Definition of "done" for each task
- Success criteria for each week

**Time to read:** 20 minutes

---

### 3. **PHASE_1_SPEC.md** (Optional Reference)
**Read this if:** You want to understand the broader product roadmap  
**Note:** This is XP/Levels/Badges (Phase 1), not blocking Brightspace work  
**When to read:** After Brightspace integration complete

---

## Quick Reference: What to Code First

```
START HERE: IMMEDIATE_NEXT_STEPS.md

Week 1:
  Task 1.1 → EVOKE Identity System (POST endpoints to link IDs)
  Task 1.2 → Submission tracking table (database)
  Task 1.3 → Badge-Brightspace mapping (database)

Week 2-3:
  Task 2.1 → BrightspaceLMS class (production adapter)
  Task 2.2 → Mission-Assignment mapping (database)
  Task 2.3 → Integrate into submit-evidence endpoint

Week 3-4:
  Task 3.1 → LTI login provider (JWT verification)
  Task 3.2 → LTI launch endpoint (full flow)
  Task 4.1 → Grading webhook (teacher sync)
  Task 4.2 → End-to-end test

Environment:
  - Update .env with Brightspace credentials
  - Add PyJWT to requirements.txt
```

---

## Testing Strategy

### Local Testing (Week 1-3)
Use the Brightspace simulator while building:
```bash
# Start simulator
cd brightspace-sim
python -m uvicorn app:app --port 8001

# Test identity endpoint
curl -X POST http://localhost:8000/api/identity/link-brightspace \
  -H "Content-Type: application/json" \
  -d '{"evoke_user_id":"uuid","brightspace_user_id":6001,"access_token":"token"}'
```

### Integration Testing (Week 3-4)
Test against real Brightspace (sandbox):
```bash
# Set environment variable
export BRIGHTSPACE_SIMULATOR_MODE=false
export BRIGHTSPACE_TENANT_URL=https://school.brightspace.com
export BRIGHTSPACE_APP_KEY=<key>
export BRIGHTSPACE_APP_SECRET=<secret>

# Run end-to-end test
pytest tests/test_e2e_brightspace.py -v
```

### Fallback Strategy
If real Brightspace unavailable:
```python
# In code: automatically falls back to simulator
if BRIGHTSPACE_SIMULATOR_MODE or not BRIGHTSPACE_CONFIGURED:
    lms = BrightspaceSimulator()
else:
    lms = BrightspaceLMS(...)
```

---

## Critical Dependencies

### Environment Variables (Required for Week 2+)
```bash
BRIGHTSPACE_TENANT_URL=https://school.brightspace.com
BRIGHTSPACE_APP_KEY=<register-with-school-admin>
BRIGHTSPACE_APP_SECRET=<register-with-school-admin>
BRIGHTSPACE_ORG_UNIT_ID=<course-id-from-brightspace>
```

### Python Packages (Add to requirements.txt)
```
PyJWT==2.8.1          # For LTI 1.3 JWT validation
cryptography==42.0.0  # For key handling
```

### Brightspace Setup (Needed by Week 3)
1. **Register LTI Tool** in Brightspace admin
   - Tool ID: (generates a GUID)
   - Launch URL: `https://evoke.school.local/api/lti/launch`
   - Public key: (paste from Brightspace)

2. **Get OAuth 2.0 Credentials**
   - App Key: (from admin registration)
   - App Secret: (from admin registration)
   - Scope: `awards:_:_` + `courses:_:_`

3. **Create Test Assignments** in Brightspace
   - Mission 1 (m1): "Follow the Flow"
   - Mission 2 (m2): "Money Moves"
   - Mission 3 (m3): "Building Blocks"

---

## Success Criteria (Week 4)

Your code is production-ready when:

- ✅ Student launches EVOKE from Brightspace (LTI)
- ✅ Auto-logged in, identity linked
- ✅ Submits evidence → syncs to Brightspace dropbox
- ✅ AI awards common badge immediately
- ✅ Teacher grades in Brightspace → epic/legendary awarded
- ✅ Student opens Minecraft companion → collects award
- ✅ Item appears in Minecraft inventory (RCON delivery)
- ✅ All badges visible in Brightspace gradebook
- ✅ Zero data loss on Brightspace downtime (queue for retry)

---

## Daily Standup Template

Use this to track progress:

```markdown
## Day N Status

**Today:**
- [x] Task X.X (describe what got done)
- [ ] Task Y.Y (blocked by Z)

**Blockers:**
- None / Waiting for Brightspace sandbox access

**Next:**
- Task Z.Z (estimated X hours)

**Metrics:**
- Commits: N
- Tests passing: N/M
- Lines of code: +N
```

---

## Rollout After Week 4

Once Brightspace integration is complete:

1. **Pilot School Deployment** (Week 5)
   - Load real Brightspace tenant credentials
   - Register LTI tool in their Brightspace
   - Create test course with EVOKE assignments
   - Test with 10 students

2. **Phase 1 Rollout** (Week 6+)
   - Add XP/Levels/Badges (see PHASE_1_SPEC.md)
   - Teacher dashboard for monitoring
   - Full 50-student pilot

3. **Production Ready** (Week 12+)
   - Multi-school deployment
   - Monitoring/alerting
   - Scale to 1000+ students

---

## Reference Quick Links

| Document | Purpose | Read Time |
|----------|---------|-----------|
| BRIGHTSPACE_INTEGRATION_SPEC.md | Full architecture | 15 min |
| IMMEDIATE_NEXT_STEPS.md | Task-by-task breakdown | 20 min |
| PHASE_1_SPEC.md | XP/Levels/Badges design | 30 min |
| docs/process/thread3.md | Brightspace API reference | 20 min |
| ARCHITECTURE.md | System design rationale | 10 min |

---

## What NOT to Do Yet

🚫 **Don't start Phase 1 (XP/Levels)** until Brightspace works  
🚫 **Don't build team collaboration** until identity system working  
🚫 **Don't do UI redesign** until teachers can use it  
🚫 **Don't scale to 100+ students** until grading webhook tested  

**Why:** Every task depends on working Brightspace integration.

---

## When You're Stuck

1. **Syntax error?** → Check syntax highlighting in your editor
2. **Type error?** → Run `mypy` to catch type mismatches early
3. **Database error?** → Check schema in PostgreSQL: `\d submissions`
4. **API error?** → Test against brightspace-sim first (easier to debug)
5. **Integration failing?** → Enable verbose logging + check `.claude` logs

---

## Questions?

**Q: Do I need real Brightspace to start?**  
A: No. Use the simulator (Week 1-2), then integrate real Brightspace (Week 2-3).

**Q: What if Brightspace API changes?**  
A: Keep simulator updated; it's your contract. Adapter code changes won't break tests.

**Q: Can I do Phase 1 (XP) in parallel?**  
A: No. Brightspace is critical path. Phase 1 can start after Task 3.2 (LTI endpoint) works.

**Q: How much backend knowledge do I need?**  
A: Medium. Async Python, FastAPI, PostgreSQL, OAuth 2.0. All documented in task descriptions.

---

## Timeline Summary

```
Week 1: Foundation        (Identity + DB tables) → 4 hours
Week 2-3: Integration     (BrightspaceLMS + sync) → 8 hours
Week 3-4: Auth + Grading  (LTI + webhook + test) → 8 hours
─────────────────────────────────────────────────
Total: ~20 hours over 4 weeks = 5 hrs/week

Then: 2-3 weeks Phase 1 (XP/Levels/Badges)
Then: 2-3 weeks Phase 2 (Timeline/Portfolio)
...
Total to production: 12 weeks (3 months)
```

---

**Ready?** Start with Task 1.1 in `IMMEDIATE_NEXT_STEPS.md`. Come back here if you need the big picture.

**Next Step:** Open `IMMEDIATE_NEXT_STEPS.md` and start Task 1.1 (EVOKE Identity System).
