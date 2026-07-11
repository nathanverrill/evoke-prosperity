# Brightspace LMS Integration Specification

**Status:** API simulator complete → Ready to implement real integration  
**Based on:** Brightspace API (July 2026) from `docs/process/thread3.md`  
**Next Step:** Implement `BrightspaceLMS` adapter for production use

---

## What's Done

✅ **Brightspace API Simulator** (`brightspace-sim/brightspace_api.py`)
- In-memory Brightspace LMS for testing EVOKE integration
- Implements OAuth 2.0 token flow
- Identity endpoints (whoami, get user)
- Award Service (BAS) - badge issuance/retrieval
- Group management - create categories, groups, add members
- Dropbox (assignment) submission and grading
- Fully self-contained, no external dependency

✅ **Test Server** (`brightspace-sim/app.py`)
- FastAPI wrapper for simulator
- Teacher review UI for testing grading flow
- Admin endpoints for inspection/testing
- Ready to demo end-to-end flow

---

## What Needs to Be Built (Your Coding Queue)

### 1. EVOKE Core ID System (2-3 days)

**Goal:** Map Brightspace UserId ↔ Minecraft UUID ↔ EVOKE ID

**What to code:**

Add to `evoke/main.py`:

```python
# New table: evoke_identities
# - evoke_id (UUID, primary key)
# - user_id (UUID, foreign key to users table)
# - brightspace_user_id (integer, from Brightspace API)
# - minecraft_uuid (string, from Minecraft)
# - created_at TIMESTAMP

# Endpoints:
POST /api/identity/link-brightspace
  {
    "evoke_id": "uuid",
    "brightspace_user_id": 6001,
    "access_token": "brightspace-token"
  }
  → Verifies token via Brightspace /d2l/api/lp/1.96/users/whoami
  → Maps and stores link
  → Returns evoke_id for future use

GET /api/identity/{evoke_id}
  → Returns mapped IDs (brightspace_user_id, minecraft_uuid)

GET /api/identity/by-brightspace/{bs_user_id}
  → Returns evoke_id for a Brightspace user
  → Used during LTI login

POST /api/identity/link-minecraft
  {
    "evoke_id": "uuid",
    "minecraft_uuid": "uuid",
    "minecraft_username": "username"
  }
  → Links Minecraft UUID to EVOKE ID
```

**Why:** Glues all three systems together. Nothing else can work without this.

---

### 2. BrightspaceLMS Adapter (5-7 days)

**Goal:** Production-ready Brightspace integration (replaces simulator)

**What to code:**

Create `evoke/lms/brightspace_lms.py`:

```python
from typing import Protocol

class LMSSync(Protocol):
    """LMS adapter interface from ARCHITECTURE.md"""
    
    def submit_assignment(self, user: User, mission: Mission, file: bytes) -> None:
        """
        POST /d2l/api/lp/{version}/dropbox/{assignmentId}/submissions
        
        Implementation:
        1. Get brightspace_user_id from evoke_identities
        2. POST to Brightspace dropbox endpoint
        3. Log submission_id for webhook tracking
        """
        pass
    
    def push_badge_award(self, user: User, badge: Badge) -> None:
        """
        POST /d2l/api/bas/{version}/orgunits/{orgUnitId}/issued/
        
        Implementation:
        1. Get brightspace_user_id from evoke_identities
        2. Look up award_id for this badge (new table: badge_brightspace_mapping)
        3. POST to Award Service (BAS)
        4. Handle idempotency: don't re-issue if already awarded
        """
        pass
    
    def push_mission_status(self, user: User, mission: Mission, status: str) -> None:
        """
        PUT /d2l/api/lp/{version}/dropbox/{assignmentId}/submissions/{submissionId}/grade
        
        Implementation:
        1. Get submission_id from submissions table
        2. Map EVOKE status to Brightspace grade:
           - "Completed" → 100
           - "Needs Revision" → 50
           - "In Progress" → 0 (draft)
        3. Fetch latest feedback/comments
        4. PUT grade with feedback
        """
        pass

class BrightspaceLMS:
    def __init__(self, tenant_url: str, app_key: str, app_secret: str):
        """
        Initialize with Brightspace tenant credentials
        
        Required env vars:
        - BRIGHTSPACE_TENANT_URL="https://school.brightspace.com"
        - BRIGHTSPACE_APP_KEY="app-key-from-admin"
        - BRIGHTSPACE_APP_SECRET="app-secret-from-admin"
        """
        self.tenant_url = tenant_url
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = None  # Obtained via OAuth 2.0 service account
        self.token_expires_at = None
```

**New tables needed:**

```sql
CREATE TABLE badge_brightspace_mapping (
    badge_id UUID REFERENCES badges(id),
    brightspace_award_id INTEGER,
    campaign_id UUID REFERENCES campaigns(id),
    UNIQUE(badge_id, campaign_id)
);

CREATE TABLE submissions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    mission_id UUID REFERENCES missions(id),
    brightspace_submission_id VARCHAR(255),  -- from API
    submitted_at TIMESTAMP,
    graded_at TIMESTAMP,
    grade INTEGER
);
```

**OAuth 2.0 Service Account:**

For `push_badge_award` and `push_mission_status`, we need server-to-server auth (user not present):

```python
def get_service_account_token(self):
    """
    OAuth 2.0 "client credentials" flow
    
    POST {tenant_url}/oauth2/token
    {
        "client_id": app_key,
        "client_secret": app_secret,
        "grant_type": "client_credentials",
        "scope": "awards:_:_ courses:_:_"
    }
    
    Returns: access_token, expires_in
    """
    pass
```

---

### 3. LTI 1.3 Login Integration (5-7 days)

**Goal:** Students launch EVOKE from Brightspace course, get auto-logged in

**What to code:**

Implement `evoke/lti/brightspace_lti_provider.py`:

```python
from evoke.identity import IdentityProvider

class BrightspaceLTIProvider(IdentityProvider):
    """LTI 1.3 Platform integration per docs/process/thread3.md"""
    
    def login(self, lti_launch_request: dict) -> User:
        """
        Handle LTI 1.3 platform launch
        
        Flow:
        1. Receive LTI launch request (POST /api/lti/launch)
        2. Verify JWT signature using Brightspace public key
        3. Extract claims:
           - sub (Brightspace user_id)
           - email
           - name
           - https://purl.imsglobal.org/spec/lti/claim/roles
        4. Look up or create user in evoke_identities
        5. Create session token
        6. Redirect to /api/missions (auto-logged in)
        """
        pass
```

**New endpoint:**

```python
POST /api/lti/launch
  (JWT in Authorization header)
  
  Returns:
  {
    "user_id": "uuid",
    "session_token": "token",
    "redirect_to": "/api/missions"
  }
```

**Required Brightspace Configuration:**
- LTI Tool ID registration in Brightspace admin
- Public key exchange (Brightspace provides, we store)
- Redirect URI: `https://evoke.school.local/api/lti/launch`

---

### 4. Webhook for Teacher Grading (2-3 days)

**Goal:** When teacher grades in Brightspace, sync back to EVOKE

**What to code:**

```python
# Enhance: POST /api/webhooks/brightspace/review

def brightspace_review_webhook(
    submission_id: str,
    user_id: int,  # Brightspace user_id
    grade: int,
    feedback: str
):
    """
    Webhook called by Brightspace when teacher grades
    (or called by our poll loop if Brightspace doesn't support webhooks)
    
    Flow:
    1. Look up EVOKE user via brightspace_user_id from evoke_identities
    2. Look up mission_id from submissions.brightspace_submission_id
    3. Call push_mission_status() to update EVOKE
    4. Publish event: TeacherReviewed (existing event)
    5. Trigger award: if grade ≥ 90: legendary, elif ≥ 80: epic
    """
    pass
```

---

### 5. Group Sync with Brightspace (2-3 days)

**Goal:** Teams created in EVOKE auto-create Brightspace groups

**What to code:**

Hook into `POST /api/teams` (existing endpoint):

```python
# When team created:
# 1. Call brightspace_lms.create_group_category(name="Evoke Teams")
# 2. Call brightspace_lms.create_group(category_id, team_name)
# 3. For each team member:
#    - Get brightspace_user_id from evoke_identities
#    - Call brightspace_lms.enroll_user_in_group(group_id, brightspace_user_id)
# 4. Store brightspace_group_id in teams table

ALTER TABLE teams ADD COLUMN brightspace_group_id VARCHAR(255);
```

---

## Integration Test Plan

Once all 5 components are built:

```
Test scenario: End-to-end LTI launch → submit evidence → teacher grade → award

1. Student launches EVOKE from Brightspace (LTI)
   ✓ LTI login creates session
   ✓ Brightspace user_id linked to EVOKE user_id

2. Student submits mission evidence
   ✓ File stored in MinIO
   ✓ Brightspace dropbox submission created
   ✓ Common-tier award granted

3. AI reviews submission
   ✓ Epic-tier award granted (if consistent)

4. Teacher grades in Brightspace
   ✓ Webhook received (or poll detects grade)
   ✓ Legendary-tier award granted

5. Student collects award in Minecraft
   ✓ RewardCollected event triggers
   ✓ Minecraft Reward Bridge delivers item via RCON

6. All awards appear in Brightspace gradebook
   ✓ Badges synced back to Brightspace BAS
   ✓ Grade reflects completion status
```

---

## Environment Setup (Required)

Before coding, schools must configure:

```bash
# .env (or environment variables)
BRIGHTSPACE_TENANT_URL=https://school.brightspace.com
BRIGHTSPACE_APP_KEY=<from-admin-registration>
BRIGHTSPACE_APP_SECRET=<from-admin-registration>
BRIGHTSPACE_ORG_UNIT_ID=<course-evoke-prosperity-id>

# LTI 1.3 configuration in Brightspace:
# - Tool ID (GUID)
# - Public key (from Brightspace)
# - Redirect URL: https://evoke.school.local/api/lti/launch
```

---

## Code to Remove/Replace

✅ **SimulatedBrightspaceLMS** → Replace with real `BrightspaceLMS` in main.py
- Keep simulator for testing/CI
- Set env var: `BRIGHTSPACE_SIMULATOR_MODE=true` for test runs

✅ **LocalIdentityProvider login endpoint** → Enhance to support both local (dev) + LTI (prod)

---

## Dependencies to Add

```
requirements.txt:
- PyJWT (for LTI 1.3 JWT validation)
- requests (for Brightspace API calls)
- cryptography (for key handling)
```

---

## Estimation & Sequencing

| Component | Effort | Duration | Dependencies |
|-----------|--------|----------|--------------|
| 1. EVOKE ID System | 5 days | Week 1 | None |
| 2. BrightspaceLMS | 6 days | Week 2 | #1 |
| 3. LTI 1.3 Login | 6 days | Week 2 | #1 |
| 4. Webhook/Polling | 3 days | Week 3 | #2 |
| 5. Group Sync | 3 days | Week 3 | #2 |
| Integration Test | 2 days | Week 3 | All |

**Critical Path:** 1 → 2 → 3 → (4 & 5 parallel) → Test

**Total:** ~4 weeks for production-ready Brightspace integration

---

## Notes

- **Idempotency is critical:** Always check if badge/grade already exists before issuing
- **Sandbox first:** Use Brightspace sandbox tenant for testing; prod only after verified
- **Token refresh:** Service account tokens expire; implement auto-refresh
- **Error handling:** Network timeouts to Brightspace should not break EVOKE flow (queue for retry)
- **Logging:** All Brightspace API calls must be logged (audit trail)

---

## Reference

- Brightspace API docs: `/docs/process/thread3.md`
- Identity provider interface: `ARCHITECTURE.md` "Identity & LMS integration"
- LMS sync interface: `ARCHITECTURE.md` "Identity & LMS integration"
- LTI 1.3 spec: https://www.imsglobal.org/spec/lti/v1p3/
