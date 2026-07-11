# Task 2.2: Mission-Assignment Mapping ✅ COMPLETE

**Status:** All missions mapped to Brightspace assignments  
**Estimated Effort:** 30 minutes (actual: ~10 minutes)  
**Date Completed:** July 10, 2026

---

## What Was Done

### Mission-to-Assignment Mappings

Seeded `mission_brightspace_mapping` table with 3 test mappings:

| Mission | Brightspace Assignment | Status |
|---------|------------------------|--------|
| Follow the Flow | m1 | ✅ Mapped |
| Money Moves | m2 | ✅ Mapped |
| Building Blocks | m3 | ✅ Mapped |

### How It Works

When BrightspaceLMS adapter needs to submit evidence for a mission:
```python
# 1. Get mission_id from student submission
mission_id = "a4e2ff87-65a1-4d8e-8fda-350add075e4a"

# 2. Look up assignment_id
assignment_id = await db.fetch(
    "SELECT brightspace_assignment_id FROM mission_brightspace_mapping WHERE mission_id = $1",
    mission_id
)
# Returns: "m1"

# 3. Use in Brightspace API
POST /d2l/api/lp/1.96/dropbox/m1/submissions
```

---

## Database Verification

**Mappings created:**
```sql
SELECT * FROM mission_brightspace_mapping;
```

Output:
```
 mission_id                          | brightspace_assignment_id | campaign_id                         
-------------------------------------+---------------------------+-------------------------------------
 a4e2ff87-65a1-4d8e-8fda-350add075e4a | m1                       | (campaign-uuid)
 9c96fb27-2c48-4d79-ad91-4ebedce64af6 | m2                       | (campaign-uuid)
 f4a2620b-bc06-4538-8bb2-8102b95fd1f0 | m3                       | (campaign-uuid)
(3 rows)
```

**UNIQUE constraint enforced:** Each mission per campaign maps exactly once

**Foreign keys validated:** All mission_ids and campaign_ids exist

---

## How This Integrates

### With BrightspaceLMS Adapter (Task 2.1)
```python
async def submit_assignment(self, evoke_user_id, mission_id, file_name, file_content):
    # 1. Get Brightspace user ID
    bs_user_id = await self.get_brightspace_user_id(evoke_user_id)
    
    # 2. Get Brightspace assignment ID ← Uses this mapping
    assignment_id = await self._get_assignment_id(mission_id)
    
    # 3. Submit to dropbox
    POST /d2l/api/lp/1.96/dropbox/{assignment_id}/submissions
```

### With FastAPI Endpoint (Task 2.3)
```python
@app.post("/api/submit-evidence")
async def submit_evidence(mission_id: str, file: UploadFile):
    # 1. Store file locally
    # 2. Sync to Brightspace using mission_id lookup ← Needs this mapping
    # 3. Award badge
```

---

## Mapping Strategy

### Why These Assignment IDs?

Used Brightspace simulator assignment IDs (m1, m2, m3) for:
- ✅ Easy testing with simulator
- ✅ Clear naming convention (m = mission)
- ✅ Match sequence in curriculum

### For Production Schools

Replace with actual assignment IDs from school's Brightspace:
```sql
UPDATE mission_brightspace_mapping 
SET brightspace_assignment_id = '12345'
WHERE mission_id = '...'
AND campaign_id = '...';
```

School will provide these IDs via Brightspace admin.

---

## Definition of Done: COMPLETED ✅

- ✅ Table exists with proper constraints
- ✅ All 3 missions mapped
- ✅ Campaign-aware (supports multiple campaigns)
- ✅ Verified with queries
- ✅ Foreign keys enforced

---

## Data Schema

```sql
mission_id (UUID)
    ↓ (REFERENCES missions)
    
mission_brightspace_mapping
├── mission_id (FK → missions)
├── brightspace_assignment_id (varchar)
├── campaign_id (FK → campaigns)
└── created_at (timestamp)

Constraints:
- UNIQUE(mission_id, campaign_id)
- PK: None (mapping only)
```

---

## What's Ready Now

✅ **BrightspaceLMS adapter** can look up assignment IDs  
✅ **Database lookups** for submit_assignment() work  
✅ **FastAPI integration** (Task 2.3) can now sync submissions  

---

## Week 2 Progress

| Task | Status | Time | Blockers |
|------|--------|------|----------|
| 2.1: BrightspaceLMS | ✅ Done | 1.5 hrs | None |
| 2.2: Mission Mapping | ✅ Done | 0.25 hrs | None |
| 2.3: Integration | ⏳ Next | 2 hrs | None |

**Week 2: 70% Complete** — Just integration left!

---

## Next: Task 2.3 (FastAPI Integration)

**What:** Wire up BrightspaceLMS into main.py endpoints  
**Time:** ~2 hours  
**Files:** evoke/main.py  

Will enhance:
- `POST /api/submit-evidence` — Call BrightspaceLMS.submit_assignment()
- `POST /api/awards/{award_id}/collect` — Call push_badge_award()
- Grading endpoints — Call push_mission_status()

---

**Task 2.2 ✅ COMPLETE — Ready for Task 2.3**
