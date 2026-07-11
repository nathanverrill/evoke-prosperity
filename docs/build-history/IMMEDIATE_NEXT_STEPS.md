# EVOKE Prosperity: Immediate Implementation Roadmap

**Status:** Brightspace API simulator complete. Ready to code production integration.  
**Timeline:** 4 weeks to real Brightspace connection  
**Goal:** End-to-end LTI launch → submit → grade → reward flow working with real Brightspace

---

## This Week (Week 1): Foundation

### Task 1.1: EVOKE Identity System
**File:** `evoke/main.py` (new section)  
**Effort:** 2-3 hours  
**What to build:**

Add database table:
```sql
CREATE TABLE evoke_identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    brightspace_user_id INTEGER UNIQUE,
    minecraft_uuid VARCHAR(36),
    minecraft_username VARCHAR(16),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, brightspace_user_id)
);
```

Add FastAPI endpoints to `evoke/main.py`:
```python
POST /api/identity/link-brightspace
  {
    "evoke_user_id": "uuid",
    "brightspace_user_id": 6001,
    "brightspace_access_token": "token"
  }
  → Verifies token via Brightspace whoami()
  → Creates identity mapping
  → Returns evoke_user_id

POST /api/identity/link-minecraft
  {
    "evoke_user_id": "uuid",
    "minecraft_uuid": "uuid",
    "minecraft_username": "playername"
  }

GET /api/identity/{evoke_user_id}
  → Returns { brightspace_user_id, minecraft_uuid, minecraft_username }

GET /api/identity/by-brightspace/{brightspace_user_id}
  → Returns { evoke_user_id }
  → Used during LTI login
```

**Test:** Run simulator locally, test the endpoints with curl
```bash
# Start simulator
cd brightspace-sim
python -m uvicorn app:app --port 8001

# In another terminal:
curl -X POST http://localhost:8000/api/identity/link-brightspace \
  -H "Content-Type: application/json" \
  -d '{
    "evoke_user_id": "550e8400-e29b-41d4-a716-446655440000",
    "brightspace_user_id": 6001,
    "brightspace_access_token": "<token-from-simulator>"
  }'
```

**Definition of Done:**
- ✅ Table created in PostgreSQL
- ✅ All 4 endpoints implemented
- ✅ Tested against brightspace-sim
- ✅ Token verification works

---

### Task 1.2: Submission Tracking Table
**File:** `evoke-infra/init-db.sql` (enhance)  
**Effort:** 1 hour  
**What to build:**

Add table to track submissions:
```sql
CREATE TABLE submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    mission_id UUID NOT NULL REFERENCES missions(id),
    brightspace_submission_id VARCHAR(255),
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_path VARCHAR(500),  -- MinIO path
    status VARCHAR(50) DEFAULT 'submitted',  -- submitted, graded, awarded
    grade INTEGER,
    feedback TEXT,
    graded_at TIMESTAMP,
    UNIQUE(user_id, mission_id, submitted_at)
);

CREATE INDEX idx_submissions_user_mission ON submissions(user_id, mission_id);
CREATE INDEX idx_submissions_brightspace_id ON submissions(brightspace_submission_id);
```

**Definition of Done:**
- ✅ Table exists in database
- ✅ Indexes created for queries
- ✅ Seed data includes sample submissions

---

### Task 1.3: Badge-Brightspace Mapping
**File:** `evoke-infra/init-db.sql` (enhance)  
**Effort:** 30 minutes  
**What to build:**

```sql
CREATE TABLE badge_brightspace_mapping (
    badge_id UUID NOT NULL REFERENCES badges(id),
    brightspace_award_id INTEGER NOT NULL,
    campaign_id UUID NOT NULL REFERENCES campaigns(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(badge_id, campaign_id)
);

-- Seed data for Evoke Prosperity campaign
INSERT INTO badge_brightspace_mapping (badge_id, brightspace_award_id, campaign_id)
SELECT 
    b.id,
    CASE 
        WHEN b.tier = 'common' THEN 1001
        WHEN b.tier = 'epic' THEN 1002
        WHEN b.tier = 'legendary' THEN 1003
    END as award_id,
    c.id
FROM badges b
JOIN campaigns c ON c.name = 'Evoke Prosperity'
WHERE b.campaign_id = c.id;
```

**Definition of Done:**
- ✅ Table created
- ✅ Seed data matches badges in each campaign
- ✅ Can query Brightspace award_id by badge_id + campaign

---

## Next Week (Week 2-3): BrightspaceLMS Adapter

### Task 2.1: BrightspaceLMS Production Adapter
**File:** `evoke/lms/brightspace_lms.py` (new)  
**Effort:** 4-5 hours  
**What to build:**

Production-ready Brightspace integration that replaces simulator:

```python
class BrightspaceLMS:
    def __init__(self, tenant_url: str, app_key: str, app_secret: str):
        self.tenant_url = tenant_url
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = None
        self.token_expires_at = None
    
    async def get_service_account_token(self) -> str:
        """OAuth 2.0 client credentials flow for server-to-server auth"""
        # POST /oauth2/token with client_id, client_secret, grant_type=client_credentials
        # Returns access_token
        pass
    
    async def push_badge_award(self, user_id: str, badge_id: str, campaign_id: str) -> bool:
        """Issue badge in Brightspace Award Service"""
        # 1. Look up brightspace_user_id from evoke_identities
        # 2. Look up brightspace_award_id from badge_brightspace_mapping
        # 3. POST to /d2l/api/bas/1.62/orgunits/{org_unit}/issued/
        # 4. Return True/False
        pass
    
    async def submit_assignment(self, user_id: str, mission_id: str, file_bytes: bytes, file_name: str) -> str:
        """Submit evidence to Brightspace dropbox"""
        # 1. Get brightspace_user_id
        # 2. Map mission_id to assignment_id (need new table)
        # 3. POST to /d2l/api/lp/1.96/dropbox/{assignment_id}/submissions
        # 4. Store submission_id in submissions table
        # 5. Return submission_id
        pass
    
    async def grade_submission(self, brightspace_submission_id: str, grade: int, feedback: str) -> bool:
        """Update grade for a submission in Brightspace"""
        # PUT /d2l/api/lp/1.96/dropbox/{assignment_id}/submissions/{submission_id}/grade
        pass
```

**Dependencies needed:**
- `httpx` (async HTTP client) — already in requirements.txt
- `PyJWT` (JWT validation for LTI) — add to requirements.txt
- Env vars: `BRIGHTSPACE_TENANT_URL`, `BRIGHTSPACE_APP_KEY`, `BRIGHTSPACE_APP_SECRET`, `BRIGHTSPACE_ORG_UNIT_ID`

**Test:** Create `tests/test_brightspace_lms.py` with mock Brightspace responses

**Definition of Done:**
- ✅ BrightspaceLMS class fully implemented
- ✅ All 4 methods have error handling + logging
- ✅ Token refresh handled correctly
- ✅ Integration tests pass with simulator

---

### Task 2.2: Mission-Assignment Mapping
**File:** `evoke-infra/init-db.sql` (enhance)  
**Effort:** 30 minutes  
**What to build:**

```sql
CREATE TABLE mission_brightspace_mapping (
    mission_id UUID NOT NULL REFERENCES missions(id),
    brightspace_assignment_id VARCHAR(50) NOT NULL,
    campaign_id UUID NOT NULL REFERENCES campaigns(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(mission_id, campaign_id)
);

-- Seed data
INSERT INTO mission_brightspace_mapping (mission_id, brightspace_assignment_id, campaign_id)
SELECT m.id, m.external_id, c.id
FROM missions m
JOIN campaigns c ON c.id = m.campaign_id
WHERE c.name = 'Evoke Prosperity';
```

**Definition of Done:**
- ✅ Table created and seeded
- ✅ Maps each mission to a Brightspace assignment ID

---

### Task 2.3: Integration into main.py
**File:** `evoke/main.py` (enhance POST /api/submit-evidence)  
**Effort:** 2 hours  
**What to build:**

When a student submits evidence:
```python
@router.post("/api/submit-evidence")
async def submit_evidence(
    mission_id: str,
    file: UploadFile,
    db: AsyncSession = Depends(get_db)
):
    # 1. Get current user from session/auth
    # 2. Store file in MinIO (existing code)
    # 3. Create submission record in database
    
    # NEW: If real Brightspace configured, sync submission
    if BRIGHTSPACE_TENANT_URL:
        brightspace_lms = BrightspaceLMS(...)
        submission_id = await brightspace_lms.submit_assignment(
            user_id=user_id,
            mission_id=mission_id,
            file_bytes=await file.read(),
            file_name=file.filename
        )
        # Store submission_id for later grading
        submission.brightspace_submission_id = submission_id
    
    # 4. Award "common" tier badge (existing code)
    # 5. Publish event: EvidenceSubmitted (existing)
    
    return { "submission_id": str(submission.id) }
```

**Definition of Done:**
- ✅ Submission syncs to Brightspace when configured
- ✅ Fallback works if Brightspace unavailable (queue for retry)
- ✅ Tested with simulator

---

## Week 3-4: LTI 1.3 Login

### Task 3.1: LTI 1.3 Login Provider
**File:** `evoke/lti/brightspace_lti_provider.py` (new)  
**Effort:** 3-4 hours  
**What to build:**

```python
class BrightspaceLTIProvider:
    def __init__(self, public_key_jwk: dict):
        self.public_key_jwk = public_key_jwk
    
    async def login(self, id_token: str) -> tuple[str, dict]:
        """
        Handle LTI 1.3 platform launch
        
        Flow:
        1. Verify JWT signature using Brightspace public key
        2. Extract claims: sub, email, name, roles
        3. Look up or create EVOKE user
        4. Create identity mapping (brightspace_user_id → evoke_user_id)
        5. Return session token
        """
        payload = jwt.decode(id_token, self.public_key_jwk, algorithms=["RS256"])
        
        # Extract claims
        brightspace_user_id = int(payload["sub"])
        email = payload.get("email")
        name = payload.get("name")
        roles = payload.get("https://purl.imsglobal.org/spec/lti/claim/roles", [])
        
        # Look up or create user
        db_user = await get_or_create_user(email, name)
        
        # Create identity mapping
        await create_identity_mapping(db_user.id, brightspace_user_id)
        
        # Create session
        session_token = create_session_token(db_user.id)
        
        return session_token, db_user
```

### Task 3.2: LTI Launch Endpoint
**File:** `evoke/main.py` (new endpoint)  
**Effort:** 1-2 hours  
**What to build:**

```python
@router.post("/api/lti/launch")
async def lti_launch(request: Request):
    """
    LTI 1.3 platform launch endpoint
    
    Brightspace sends:
    - id_token (JWT with user info)
    - client_id
    
    We respond with:
    - Redirect to /api/missions (logged in)
    """
    id_token = request.form.get("id_token")
    
    lti_provider = BrightspaceLTIProvider(...)
    session_token, user = await lti_provider.login(id_token)
    
    # Set session cookie + redirect
    return RedirectResponse(
        url="/api/missions",
        headers={"Set-Cookie": f"session={session_token}"}
    )
```

**Definition of Done:**
- ✅ LTI JWT verification works
- ✅ User auto-created on first launch
- ✅ Identity mapping created
- ✅ Session established
- ✅ Tested with simulator (create mock LTI request)

---

## Week 4: Grading Webhook & Polish

### Task 4.1: Teacher Grading Webhook
**File:** `evoke/main.py` (enhance POST /api/webhooks/brightspace)  
**Effort:** 2-3 hours  
**What to build:**

When teacher grades in Brightspace, sync back:
```python
@router.post("/api/webhooks/brightspace/grade")
async def brightspace_grade_webhook(
    submission_id: str,
    grade: int,
    feedback: str,
    brightspace_user_id: int
):
    # 1. Look up EVOKE user via evoke_identities
    # 2. Look up submission in submissions table
    # 3. Update submission.grade, submission.feedback
    # 4. Award badges based on grade:
    #    - grade >= 95: legendary
    #    - grade >= 85: epic
    #    - grade >= 70: common (already awarded at submission)
    # 5. Publish TeacherReviewed event (triggers AI review stop)
    # 6. Return success
```

**Alternative (Polling):** If Brightspace doesn't support webhooks:
```python
async def poll_brightspace_grades(db: AsyncSession):
    """
    Background task (runs every 5 minutes) to check for graded submissions
    """
    brightspace_lms = BrightspaceLMS(...)
    
    ungraded = await db.query(submissions).filter(
        status='submitted',
        brightspace_submission_id != None
    ).all()
    
    for sub in ungraded:
        grade = await brightspace_lms.get_submission_grade(sub.brightspace_submission_id)
        if grade:
            sub.grade = grade
            sub.status = 'graded'
            # Award badges...
```

**Definition of Done:**
- ✅ Webhook endpoint handles incoming grades
- ✅ Fallback polling implemented
- ✅ Badges awarded correctly based on grade
- ✅ Events published (TeacherReviewed)

---

### Task 4.2: Integration Test (End-to-End)
**File:** `tests/test_e2e_brightspace.py` (new)  
**Effort:** 2 hours  
**What to build:**

Test the full flow:
```python
async def test_lti_launch_to_minecraft_reward():
    # 1. Student launches EVOKE from Brightspace (LTI)
    session = await lti_launch(mock_brightspace_jwt)
    assert session.user_id is not None
    
    # 2. Student submits evidence
    submission = await submit_evidence(
        mission_id="mission-1",
        file=test_file,
        session=session
    )
    assert submission.brightspace_submission_id is not None
    
    # 3. AI reviews (already works)
    # ...
    
    # 4. Teacher grades in Brightspace
    await brightspace_grade_webhook(
        submission_id=submission.brightspace_submission_id,
        grade=95,
        feedback="Excellent work!"
    )
    
    # 5. Check legendary badge awarded
    awards = await get_user_awards(session.user_id)
    assert "legendary" in [a.tier for a in awards]
    
    # 6. Student collects in Minecraft
    # Verify RCON command sent
```

**Definition of Done:**
- ✅ All 6 steps pass
- ✅ Data flows correctly through all systems
- ✅ Ready for pilot school deployment

---

## Parallel Track: Environment Setup

### Task P.1: Environment Variables
**File:** `.env` + `.env.example` (enhance)  
**Effort:** 30 minutes  
**What to add:**

```bash
# Brightspace Integration (Production)
BRIGHTSPACE_SIMULATOR_MODE=false
BRIGHTSPACE_TENANT_URL=https://school.brightspace.com
BRIGHTSPACE_APP_KEY=<from-admin>
BRIGHTSPACE_APP_SECRET=<from-admin>
BRIGHTSPACE_ORG_UNIT_ID=<course-id>

# LTI 1.3 Configuration
LTI_TOOL_ID=<guid>
LTI_PUBLIC_KEY_JWK='{"kty":"RSA",...}'

# For development/testing
BRIGHTSPACE_SIMULATOR_MODE=true  # Override to use mock Brightspace
```

**Definition of Done:**
- ✅ Example file documents all required vars
- ✅ Actual .env works with brightspace-sim
- ✅ Production .env ready for school deployment

---

## Success Criteria (End of Week 4)

✅ **Identity System:** User can link Brightspace ↔ EVOKE ↔ Minecraft  
✅ **LTI Login:** Student launches from Brightspace, auto-logged in  
✅ **Evidence Sync:** Student submits → appears in Brightspace dropbox  
✅ **AI Review:** Common badge awarded automatically  
✅ **Teacher Grading:** Teacher grades in Brightspace → Epic/Legendary awarded  
✅ **Minecraft Delivery:** Student collects award → item appears in-game  
✅ **Brightspace Gradebook:** Badges visible in Brightspace award widget  

**End Result:** Real school can use EVOKE + real Brightspace together

---

## Code Quality Checklist (Each Task)

- ✅ Type hints on all functions (Python 3.10+ style)
- ✅ Docstrings (one-liner minimum, full for complex logic)
- ✅ Error handling (HTTPException for API errors, logging)
- ✅ Logging (debug for flow, info for milestones, error for failures)
- ✅ Tests (unit + integration, use simulator as mock)
- ✅ No TODOs (if it's not done, don't commit)

---

## Resources

- **Brightspace API:** `/docs/process/thread3.md`
- **LTI 1.3 Spec:** https://www.imsglobal.org/spec/lti/v1p3/
- **Integration Spec:** `BRIGHTSPACE_INTEGRATION_SPEC.md`
- **Simulator:** `brightspace-sim/app.py` + `brightspace_api.py`
- **Phase 1 Spec:** `PHASE_1_SPEC.md` (for reference, not blocking Brightspace work)

---

## Rollback Plan

If Brightspace integration breaks:
1. Set `BRIGHTSPACE_SIMULATOR_MODE=true` (falls back to mock)
2. All endpoints keep working locally
3. No data loss (submissions still stored in EVOKE)
4. Can iterate on fix without blocking students

---

**Next:** Start Task 1.1 (EVOKE Identity System). Once complete, can work in parallel: Task 1.2 + 1.3 (database) + Task 2.1 (BrightspaceLMS adapter).
