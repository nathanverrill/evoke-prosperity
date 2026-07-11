# Task 4.2: End-to-End Integration Testing 🧪

**Objective:** Validate complete Brightspace ↔ EVOKE ↔ Minecraft workflow  
**Scope:** Happy path, error scenarios, load testing, security validation  
**Duration:** 2-3 hours  
**Date Started:** July 10, 2026

---

## Test Categories

### 1. Happy Path (Complete Workflow) ✅
**Goal:** Verify entire student journey works end-to-end

**Scenario:** Student launches EVOKE from Brightspace, submits evidence, teacher grades, student collects award

**Test Steps:**

```
Phase 1: LTI Launch & Authentication
┌─────────────────────────────────────────────────────────────┐
│ 1. Student in Brightspace                                   │
│    └─ Clicks "Launch EVOKE" button                          │
│                                                              │
│ 2. Brightspace POSTs signed JWT to /api/lti/launch          │
│    ├─ Endpoint: POST /api/lti/launch                        │
│    ├─ Payload: id_token (JWT)                               │
│    └─ Expected: HTTP 302 redirect                           │
│                                                              │
│ 3. EVOKE verifies JWT                                       │
│    ├─ Check RS256 signature ✓                               │
│    ├─ Validate audience ✓                                   │
│    ├─ Validate issuer ✓                                     │
│    └─ Extract claims ✓                                      │
│                                                              │
│ 4. User auto-provisioned                                    │
│    ├─ Create user if new                                    │
│    ├─ Link to Brightspace ✓                                 │
│    └─ Return session_token                                  │
│                                                              │
│ 5. Browser redirected to /api/missions                      │
│    ├─ HTTP 302 Location header                              │
│    ├─ Set-Cookie: session_token (HttpOnly)                  │
│    └─ Student authenticated ✓                               │
└─────────────────────────────────────────────────────────────┘

Phase 2: Evidence Submission
┌─────────────────────────────────────────────────────────────┐
│ 1. Student views missions                                   │
│    └─ GET /api/missions?user_id=...                         │
│                                                              │
│ 2. Student submits evidence                                 │
│    ├─ POST /api/submit-evidence                             │
│    ├─ Payload: mission_id, evidence_url, etc.              │
│    └─ Authenticated via session_token cookie                │
│                                                              │
│ 3. EVOKE processes submission                               │
│    ├─ Store in submissions table ✓                          │
│    ├─ Look up Brightspace user_id (evoke_identities) ✓     │
│    └─ Call BrightspaceLMS.submit_assignment()               │
│                                                              │
│ 4. Evidence syncs to Brightspace                            │
│    ├─ POST to Brightspace dropbox                           │
│    ├─ Save brightspace_submission_id in EVOKE ✓             │
│    └─ Confirmation returned ✓                               │
│                                                              │
│ 5. Common badge issued                                      │
│    ├─ INSERT INTO awards (tier=common, source=submission)   │
│    ├─ Call BrightspaceLMS.push_badge_award() ✓             │
│    ├─ Badge appears in Brightspace Award Service ✓         │
│    └─ Notification sent ✓                                   │
└─────────────────────────────────────────────────────────────┘

Phase 3: Teacher Grading
┌─────────────────────────────────────────────────────────────┐
│ 1. Teacher in Brightspace                                   │
│    └─ Grades submission (e.g., 95/100)                      │
│                                                              │
│ 2. Brightspace sends webhook                                │
│    ├─ POST /api/webhooks/brightspace/grade                  │
│    ├─ Payload: submission_id, brightspace_user_id, grade    │
│    └─ (or polling fetches grade via GET /poll)             │
│                                                              │
│ 3. EVOKE processes grade                                    │
│    ├─ Look up EVOKE user via brightspace_user_id ✓          │
│    ├─ Find submission record ✓                              │
│    └─ UPDATE submissions SET grade = 95 ✓                   │
│                                                              │
│ 4. Badge tier determined                                    │
│    ├─ Grade 95 >= 95 → LEGENDARY ✓                          │
│    └─ (Or 85-94 → EPIC, <85 → common)                       │
│                                                              │
│ 5. Epic/Legendary badge awarded                             │
│    ├─ INSERT INTO awards (tier=legendary, source=grade) ✓   │
│    ├─ No duplicates (UNIQUE constraint) ✓                   │
│    └─ Idempotency check (webhook called twice) ✓            │
│                                                              │
│ 6. Badge syncs to Brightspace                               │
│    ├─ Call BrightspaceLMS.push_badge_award() ✓             │
│    ├─ Legendary badge in Award Service ✓                    │
│    └─ Student notified ✓                                    │
│                                                              │
│ 7. Event published                                          │
│    ├─ Redpanda: TeacherReviewed event ✓                     │
│    └─ Triggers AI, notifications, analytics                │
└─────────────────────────────────────────────────────────────┘

Phase 4: Reward Collection
┌─────────────────────────────────────────────────────────────┐
│ 1. Student sees notification                                │
│    └─ New legendary badge awarded                           │
│                                                              │
│ 2. Student collects award                                   │
│    ├─ POST /api/awards/{award_id}/collect                   │
│    └─ Authenticated via session_token                       │
│                                                              │
│ 3. Reward delivered                                         │
│    ├─ RCON to Minecraft server ✓                            │
│    ├─ Items/effects given ✓                                 │
│    ├─ XP awarded ✓                                          │
│    └─ Collection marked complete ✓                          │
│                                                              │
│ 4. Verification                                             │
│    └─ Student sees rewards in Minecraft                     │
└─────────────────────────────────────────────────────────────┘
```

**Verification Checklist:**
- [ ] JWT verified (signature + expiration)
- [ ] User auto-created if new
- [ ] Session cookie set (HttpOnly, Secure)
- [ ] Evidence stored in DB
- [ ] Evidence synced to Brightspace dropbox
- [ ] Common badge issued locally
- [ ] Common badge synced to Brightspace
- [ ] Grade synced back to EVOKE
- [ ] Epic/legendary badge awarded
- [ ] Badge synced to Brightspace
- [ ] Notification created
- [ ] Reward delivered to Minecraft
- [ ] XP awarded

---

### 2. Error Scenarios 🔴

#### Scenario 2.1: Invalid JWT

**Test:** POST /api/lti/launch with:
- Expired JWT
- Wrong signature
- Invalid issuer
- Invalid audience

**Expected:** 401 response, no user created

```bash
curl -X POST http://localhost:8000/api/lti/launch \
  -F id_token="eyJhbGciOiJSUzI1NiIsImtpZCI6ImludmFsaWQifQ..."
# Expected: {"status": "error", "message": "JWT verification failed"}
```

**Verification:**
- [ ] Request rejected with 401
- [ ] No user created in DB
- [ ] Error logged

#### Scenario 2.2: Missing User Link

**Test:** Webhook for user not linked to EVOKE

**Setup:**
1. Grade a submission from unknown Brightspace user_id
2. User not in evoke_identities

**Expected:** Webhook fails gracefully, no error returned to Brightspace

```bash
curl -X POST http://localhost:8000/api/webhooks/brightspace/grade \
  -F submission_id=bs-sub-999 \
  -F brightspace_user_id=9999 \
  -F grade=95
# Expected: {"status": "error", "message": "User not linked"}
# DB: No update made
```

**Verification:**
- [ ] Webhook returns error
- [ ] No submission updated
- [ ] No award created
- [ ] Error logged (not fatal)
- [ ] Retry manually after user links (re-launch LTI)

#### Scenario 2.3: Brightspace API Unavailable

**Test:** Submit evidence while Brightspace is down

**Setup:** Mock Brightspace as unreachable

**Expected:** Evidence stored locally, award created, sync fails gracefully

```python
# Evidence submission succeeds locally
POST /api/submit-evidence
→ Submission stored in DB ✓
→ Award created ✓
→ Brightspace sync fails (network error)
→ System continues ✓
→ User notified to retry
```

**Verification:**
- [ ] Evidence stored in DB
- [ ] Common badge awarded
- [ ] Sync error logged
- [ ] System doesn't crash
- [ ] Manual retry works later (when Brightspace recovers)

#### Scenario 2.4: Duplicate Webhook Calls

**Test:** Webhook called twice for same grade

**Setup:**
1. Grade webhook called with grade=95
2. Award created (legendary)
3. Same webhook called again

**Expected:** Second call updates submission but doesn't create duplicate award

```bash
# Call 1
POST /api/webhooks/brightspace/grade
  submission_id: bs-sub-001
  grade: 95
→ submission updated ✓
→ award created (id=1) ✓

# Call 2 (duplicate)
POST /api/webhooks/brightspace/grade
  submission_id: bs-sub-001
  grade: 95
→ submission updated ✓
→ award NOT created (UNIQUE constraint prevents it) ✓
→ Return 200 OK ✓
```

**Verification:**
- [ ] Only 1 award created
- [ ] Submission updated
- [ ] No error returned (idempotent)
- [ ] DB constraint prevents duplicate

#### Scenario 2.5: Concurrent Requests

**Test:** Two simultaneous LTI launches from same Brightspace user

**Setup:**
1. User launches EVOKE in 2 browser tabs simultaneously
2. Both POSTs reach server at same time

**Expected:** Both resolve correctly, ON CONFLICT handles it

```
Request 1: POST /api/lti/launch
Request 2: POST /api/lti/launch  (same user_id)
→ Both verify JWT successfully
→ INSERT evoke_identities ON CONFLICT DO UPDATE
→ Both get session_token
→ No error ✓
```

**Verification:**
- [ ] Both requests succeed
- [ ] Only 1 user entry in DB
- [ ] Both get valid session tokens
- [ ] No race condition errors

---

### 3. Load Testing ⚡

**Goal:** Validate system handles 100+ concurrent users

#### Scenario 3.1: Concurrent LTI Launches

**Setup:**
- Simulate 100 simultaneous student launches
- Each launch: JWT verification + user provisioning + session creation

**Tools:** Apache JMeter, Locust, or custom script

```bash
# Using Locust (Python-based load testing)
locust -f tests/load_test_lti_launch.py \
  --host=http://localhost:8000 \
  --users=100 \
  --spawn-rate=10 \
  --run-time=5m
```

**Metrics to Monitor:**
- Requests/second: 100+ launches/min
- Response time: <500ms p95
- Success rate: 100% (no timeouts)
- Database connections: Stays within pool limit
- Memory: No leaks

**Expectations:**
- [ ] All 100 launches succeed
- [ ] Response time <1s per launch
- [ ] Database pool handles concurrency
- [ ] No connection timeouts

#### Scenario 3.2: Concurrent Evidence Submissions

**Setup:**
- 50 students simultaneously submit evidence
- Each submission: DB write + Brightspace sync

```bash
locust -f tests/load_test_submissions.py \
  --host=http://localhost:8000 \
  --users=50 \
  --spawn-rate=5 \
  --run-time=3m
```

**Metrics:**
- Throughput: 50+ submissions/min
- Response time: <1s p95
- Brightspace sync success: 100%
- Award creation: No duplicates

**Expectations:**
- [ ] All 50 submissions succeed
- [ ] All synced to Brightspace
- [ ] All awards created
- [ ] No database deadlocks

#### Scenario 3.3: Concurrent Grade Webhooks

**Setup:**
- 50 simultaneous grade updates
- Each grade: Lookup user + update submission + award badge + sync to Brightspace

```bash
locust -f tests/load_test_grade_webhooks.py \
  --host=http://localhost:8000 \
  --users=50 \
  --spawn-rate=5 \
  --run-time=3m
```

**Metrics:**
- Throughput: 50+ grades/min
- Response time: <500ms p95
- Award creation: No duplicates
- Brightspace sync success: 100%

**Expectations:**
- [ ] All 50 grades processed
- [ ] All awards created (no duplicates)
- [ ] All synced to Brightspace
- [ ] Database handles write concurrency

---

### 4. Security Validation 🔒

#### Scenario 4.1: JWT Signature Verification

**Test:** Attempt to forge JWT

```python
# Attempt 1: Wrong signature
jwt_token = jwt.encode(
    {"sub": "6001", "email": "attacker@evil.com"},
    "wrong_secret",  # Not the Brightspace key
    algorithm="HS256"  # Wrong algorithm
)
# Expected: Signature verification fails ✓

# Attempt 2: No signature
jwt_token = "{payload}."  # Truncated JWT
# Expected: Invalid JWT format ✓

# Attempt 3: Modified claims
jwt_token = valid_jwt.replace("learner", "admin")
# Expected: Signature verification fails ✓
```

**Verification:**
- [ ] All forgery attempts rejected
- [ ] Valid JWTs accepted
- [ ] RS256 signature required
- [ ] No claims used without verification

#### Scenario 4.2: CSRF Protection

**Test:** Attempt cross-site form submission

**Setup:**
1. Create evil.com that submits form to EVOKE
2. If user logged in, try to trigger action

**Expected:** SameSite=Lax cookie prevents cross-site submission

```html
<!-- evil.com -->
<form method="POST" action="https://evoke.school/api/submit-evidence">
  <!-- Attempt to submit evidence on user's behalf -->
</form>
```

**Expected:** Browser doesn't send session cookie (SameSite=Lax)
- [ ] POST request fails (no session_token)
- [ ] User not authenticated
- [ ] No evidence submitted

#### Scenario 4.3: XSS Protection

**Test:** Inject JavaScript via session cookie

**Expected:** HTTP-only flag prevents JavaScript access

```javascript
// Evil script on another site
console.log(document.cookie);
// Expected: session_token NOT visible (HttpOnly) ✓
// user_id and user_display_name visible (for UI) ✓
```

**Verification:**
- [ ] session_token not readable by JavaScript
- [ ] User cookies readable by frontend
- [ ] No sensitive data in readable cookies

#### Scenario 4.4: SQL Injection

**Test:** Inject SQL in API parameters

```bash
curl -X POST http://localhost:8000/api/submit-evidence \
  -F "mission_id=1' OR '1'='1" \
  -F "evidence_url=x'; DROP TABLE submissions; --"
```

**Expected:** Parameterized queries prevent injection
- [ ] Request fails validation
- [ ] No SQL executed
- [ ] Error returned safely
- [ ] Database untouched

#### Scenario 4.5: Cross-User Access

**Test:** Attempt to access another user's data

**Setup:**
1. User A logged in with session_token_A
2. Try to access User B's submissions

```bash
# User A's session
GET /api/user/b2b2b2b2/submissions?session_token=session_token_A
# Expected: Unauthorized (403) or empty result
```

**Verification:**
- [ ] Users can only access own data
- [ ] Session validates user_id
- [ ] No cross-user data leakage

#### Scenario 4.6: Brightspace User ID Spoofing

**Test:** Attempt to link wrong Brightspace user_id

**Setup:**
1. User A links to Brightspace user 100
2. Try to link to Brightspace user 200

**Expected:** Identity linking is read-only from LTI

```bash
# User A logs in via LTI (Brightspace says they're user 100)
# User A tries to submit evidence for user 200
POST /api/submit-evidence
  brightspace_user_id: 200  # Doesn't match session ✗
# Expected: Fails, uses session user instead
```

**Verification:**
- [ ] Brightspace user_id from JWT only
- [ ] Cannot override via API parameters
- [ ] User can only act as themselves

---

## Test Execution Plan

### Phase 1: Manual Testing (30 min)
1. **Setup**
   - Start local EVOKE + Brightspace simulator
   - Create test user + test mission
   - Prepare Brightspace launch JWT

2. **Happy Path (15 min)**
   - Launch from Brightspace → verify redirect
   - Submit evidence → verify sync + award
   - Simulate grade webhook → verify sync
   - Verify award in both systems

3. **Quick Error Tests (15 min)**
   - Invalid JWT → 401
   - Missing user link → error
   - Duplicate webhook → idempotent

### Phase 2: Automated Testing (60 min)
1. **Unit Tests** (already exist)
   - JWT verification
   - User provisioning
   - Award creation

2. **Integration Tests** (new)
   - Full workflow: launch → submit → grade → collect
   - Error scenarios: missing link, invalid JWT, etc.
   - Idempotency: duplicate calls

3. **Load Testing** (30 min)
   - 100 concurrent launches
   - 50 concurrent submissions
   - 50 concurrent grade webhooks
   - Monitor response times + success rate

### Phase 3: Security Validation (30 min)
1. JWT forgery attempts
2. CSRF/XSS validation
3. SQL injection attempts
4. Cross-user access attempts
5. Brightspace user spoofing

---

## Success Criteria

✅ **Functional:**
- [ ] Complete workflow succeeds end-to-end
- [ ] All error scenarios handled gracefully
- [ ] No data loss or corruption
- [ ] All integrations working

✅ **Performance:**
- [ ] 100+ concurrent users supported
- [ ] <500ms p95 response time
- [ ] 0% error rate under load
- [ ] Database connection pool stable

✅ **Security:**
- [ ] JWT verification working
- [ ] CSRF/XSS protections in place
- [ ] SQL injection prevented
- [ ] No cross-user access possible

✅ **Reliability:**
- [ ] Brightspace unavailability handled
- [ ] Webhook failures graceful
- [ ] Idempotency working
- [ ] Race conditions prevented

---

## Test Tools & Scripts

| Tool | Purpose | File |
|------|---------|------|
| Manual tests | Browser-based workflow | manual_test.sh |
| Integration tests | pytest fixtures | tests/test_integration_e2e.py |
| Load testing | Locust + JMeter | tests/load_test_*.py |
| Security tests | OWASP ZAP | tests/security_test.sh |

---

## Definition of Done

- ✅ Manual happy path test passes
- ✅ All error scenarios tested
- ✅ Load testing shows 100+ concurrent capability
- ✅ Security validation passes
- ✅ Performance benchmarks met
- ✅ No regressions introduced
- ✅ Documentation updated

---

**Next:** Implement test scripts and run through all scenarios
