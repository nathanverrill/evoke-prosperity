# Task 1.3: Badge-Brightspace Mapping ✅ COMPLETE

**Status:** Mapping table seeded with all badge-to-award associations  
**Estimated Effort:** 30 minutes (actual: ~15 minutes)  
**Date Completed:** July 10, 2026

---

## What Was Built

### 1. Database Table: `badge_brightspace_mapping`
**File:** `evoke-infra/init-db.sql` (already added in Task 1.1)

Maps EVOKE badges to Brightspace Award Service (BAS) IDs:
```sql
CREATE TABLE badge_brightspace_mapping (
    badge_id UUID NOT NULL REFERENCES badges(id),
    brightspace_award_id INTEGER NOT NULL,
    campaign_id UUID NOT NULL REFERENCES campaigns(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(badge_id, campaign_id)
);
```

**Columns:**
- `badge_id` — Which EVOKE badge (FK to badges table)
- `brightspace_award_id` — Corresponding award ID in Brightspace BAS API
- `campaign_id` — Which campaign this mapping applies to (FK to campaigns)
- `created_at` — When mapping was created
- UNIQUE constraint prevents duplicate mappings per campaign

### 2. Seed Data

**Badges Created (3 test badges):**
```
common-tier    → "Common Tier Badge"    (tier 1)
epic-tier      → "Epic Tier Badge"      (tier 2)
legendary-tier → "Legendary Tier Badge" (tier 3)
```

**Mappings (in Brightspace simulator):**
```
Badge Key          | Badge Name              | Brightspace Award ID
-------------------|-------------------------|-------------------
common-tier        | Common Tier Badge       | 1001
epic-tier          | Epic Tier Badge         | 1002
legendary-tier     | Legendary Tier Badge    | 1003
```

**Why these IDs?**
- Brightspace simulator defines awards 1001, 1002, 1003 (see `brightspace-sim/brightspace_api.py`)
- Production mapping will match actual school's Brightspace award IDs

---

## Database Verification

**Table structure:**
```
✅ badge_brightspace_mapping created
✅ UNIQUE constraint on (badge_id, campaign_id)
✅ Foreign keys to badges and campaigns
✅ Timestamps auto-tracked
```

**Seed data:**
```bash
docker compose -f evoke-infra/docker-compose.yml exec -T postgres \
  psql -U evoke -d evoke -c "
    SELECT b.key, m.brightspace_award_id 
    FROM badge_brightspace_mapping m
    JOIN badges b ON b.id = m.badge_id;"
```

Output:
```
      key       | brightspace_award_id
---------------+---------------------
 common-tier    |                 1001
 epic-tier      |                 1002
 legendary-tier |                 1003
(3 rows)
```

---

## Definition of Done: COMPLETED ✅

- ✅ **Table created** in PostgreSQL with FK constraints
- ✅ **Seed data mapped** all 3 badges to Brightspace award IDs
- ✅ **Verified** — can query award_id by badge_id + campaign
- ✅ **Campaign-aware** — supports multiple campaigns (multi-tenant ready)

---

## How It's Used

### In Task 2.1: BrightspaceLMS Adapter
When issuing a badge to a student:
```python
def push_badge_award(self, user_id: str, badge_id: str, campaign_id: str):
    # Look up Brightspace award ID
    mapping = db.query(badge_brightspace_mapping).filter_by(
        badge_id=badge_id,
        campaign_id=campaign_id
    ).first()
    
    brightspace_award_id = mapping.brightspace_award_id  # e.g., 1002
    
    # Issue in Brightspace
    POST /d2l/api/bas/1.62/orgunits/{orgUnitId}/issued/
    {
        "AwardId": brightspace_award_id,
        "IssuedToUserId": brightspace_user_id,
        "Criteria": "Completed Mission 1",
        "Evidence": "Submission ID: xyz"
    }
```

### In POST /api/awards/{award_id}/collect (existing)
When student clicks "Collect Award":
```python
# Get badge tier (already works)
award = db.query(awards).filter_by(id=award_id).first()
badge = db.query(badges).filter_by(id=award.badge_id).first()

# If configured for Brightspace sync:
if BRIGHTSPACE_ENABLED:
    # Look up corresponding Brightspace award
    bs_mapping = db.query(badge_brightspace_mapping).filter_by(
        badge_id=badge.id,
        campaign_id=campaign_id
    ).first()
    
    # Badge is already in Brightspace (issued when submitted)
    # This endpoint just marks collected locally
```

---

## Integration with Week 1 Foundation

| Task | What | Status | Connects to |
|------|------|--------|------------|
| 1.1 | Identity System | ✅ Complete | User ↔ Brightspace ↔ Minecraft |
| 1.2 | Submission Tracking | ✅ Complete | Evidence submissions + grades |
| 1.3 | Badge Mapping | ✅ Complete | Award issuance in Brightspace |

**All three tables are now ready for Task 2.1 (BrightspaceLMS Adapter)**

---

## Test Data Reference

```sql
-- Find mapping for a specific badge
SELECT brightspace_award_id 
FROM badge_brightspace_mapping 
WHERE badge_id = (SELECT id FROM badges WHERE key = 'epic-tier')
AND campaign_id = (SELECT id FROM campaigns WHERE key = 'evoke-prosperity');
-- Returns: 1002

-- Get all mappings for a campaign
SELECT 
    b.key as badge_key,
    m.brightspace_award_id,
    c.name as campaign_name
FROM badge_brightspace_mapping m
JOIN badges b ON b.id = m.badge_id
JOIN campaigns c ON c.id = m.campaign_id
WHERE c.key = 'evoke-prosperity';
```

---

## Files Modified

| File | Changes | Status |
|------|---------|--------|
| evoke-infra/init-db.sql | badge_brightspace_mapping + UNIQUE | ✅ (in 1.1) |
| (none) | Code files | N/A (DB only) |
| (none) | Badges created | Seeded in DB |
| (none) | Mappings created | Seeded in DB |

**Total:** Database only (no code changes)

---

## Configuring for Real Brightspace

When connecting to a school's real Brightspace:

```sql
-- Delete simulator mappings
DELETE FROM badge_brightspace_mapping;

-- Update with school's real award IDs
INSERT INTO badge_brightspace_mapping (badge_id, brightspace_award_id, campaign_id)
VALUES 
    (uuid_common_badge, 12345, campaign_id),   -- From school's BAS
    (uuid_epic_badge, 12346, campaign_id),
    (uuid_legendary_badge, 12347, campaign_id);
```

Ask school for their Award IDs via Brightspace admin → Awards Service

---

## Status Summary

| Component | Status | Blockers |
|-----------|--------|----------|
| Task 1.1: Identity System | ✅ Complete | None |
| Task 1.2: Submission Table | ✅ Complete | None |
| Task 1.3: Badge Mapping | ✅ Complete | None |
| **Week 1 Foundation** | **✅ 100%** | **Ready for Week 2** |

---

## Week 1 Summary

All foundational database work is complete:
- ✅ Users can link across Brightspace ↔ EVOKE ↔ Minecraft
- ✅ Submissions tracked with status and grades
- ✅ Badges mapped to Brightspace awards
- ✅ Test data seeded for manual testing

**Next:** Begin **Task 2.1 (BrightspaceLMS Adapter)** to build production integration

---

## Notes

1. **Campaign-aware design** — Mappings per campaign
   - Same badge can map to different awards in different schools
   - Supports future multi-school SaaS model

2. **Award ID mappings** — Currently hardcoded to simulator IDs
   - Production: each school provides their own award IDs
   - Same schema supports all configurations

3. **Immutable after creation** — No UPDATE on mappings
   - If wrong mapping, DELETE and re-INSERT
   - Prevents accidental award ID changes

4. **No validation on award_id** — By design
   - Brightspace credentials needed to validate
   - Validation happens at sync time (Task 2.1)

---

**Task 1.3 ✅ COMPLETE — Week 1 Database Foundation DONE**

**Next Step:** Begin Task 2.1 (BrightspaceLMS Adapter) to connect to real Brightspace
