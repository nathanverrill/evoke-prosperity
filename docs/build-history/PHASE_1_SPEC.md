# Phase 1: XP/Levels/Badges - Detailed Specification

**Duration:** 5 weeks  
**Team:** 1 Senior Backend Engineer + AI Assistant  
**Goal:** Add progression mechanics so learners see continuous advancement  
**Entry Criteria:** MVP complete and stable  
**Exit Criteria:** All 4 subsystems (XP, Levels, Superpowers, Achievements) working end-to-end

---

## Overview

This phase adds the first "visible" progression system to EVOKE. Currently, learners submit evidence and see awards—but it doesn't feel like progress. Phase 1 changes that:

**Before:** Submit evidence → get award (feels transactional)  
**After:** Submit evidence → +100 XP → level up → earn achievement badge (feels like progression)

---

## 1. XP System (1 week)

### Database Schema

Add to `users` table:
```sql
ALTER TABLE users ADD COLUMN total_xp INTEGER DEFAULT 0;
```

Create new table:
```sql
CREATE TABLE xp_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    action VARCHAR(50) NOT NULL,  -- e.g., "MissionCompleted", "LoginDaily"
    amount INTEGER NOT NULL,      -- XP to award
    context JSONB,                -- mission_id, feedback_tier, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_xp_events_user_id ON xp_events(user_id);
CREATE INDEX idx_xp_events_action ON xp_events(action);
```

### XP Actions & Values

| Action | Amount | Trigger |
|--------|--------|---------|
| LoginDaily | +5 | First activity of day |
| MissionSubmitted | +50 | Evidence uploaded |
| MissionCompleted (common tier) | +50 | Award collected |
| MissionCompleted (epic tier) | +100 | Award collected |
| MissionCompleted (legendary tier) | +150 | Award collected |
| HelpedTeammate | +20 | On peer recognition |
| ReceivedFeedback | +25 | Feedback added to submission |
| ReflectionAdded | +15 | Reflection submitted |
| QuestCompleted | +40 | Minecraft side quest |
| SkillGrowth | +10 | Superpower reaches new threshold |

### API Endpoints

#### Log XP (Internal)
```
POST /api/xp/log
Content-Type: application/json

{
  "user_id": "uuid",
  "action": "MissionCompleted",
  "amount": 100,
  "context": {
    "mission_id": "uuid",
    "tier": "epic"
  }
}

Response:
{
  "user_id": "uuid",
  "total_xp": 250,
  "new_xp": 100,
  "action": "MissionCompleted"
}
```

#### Get XP History
```
GET /api/xp/{user_id}?limit=50&offset=0

Response:
{
  "total_xp": 250,
  "xp_events": [
    {
      "id": "uuid",
      "action": "MissionCompleted",
      "amount": 100,
      "context": { "mission_id": "...", "tier": "epic" },
      "created_at": "2024-01-15T10:30:00Z"
    },
    ...
  ]
}
```

### Implementation

#### File: `evoke/xp.py` (new)

```python
from datetime import datetime, timedelta
from sqlalchemy import select, insert, func
from database import get_db_connection

class XPManager:
    def log_xp(self, user_id: str, action: str, amount: int, context: dict = None) -> dict:
        """Award XP to a user for an action."""
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            
            # Insert XP event
            cur.execute(
                """INSERT INTO xp_events (user_id, action, amount, context)
                   VALUES (%s::uuid, %s, %s, %s)""",
                (user_id, action, amount, context or {})
            )
            
            # Update user's total XP
            cur.execute(
                """UPDATE users SET total_xp = total_xp + %s
                   WHERE id = %s::uuid""",
                (amount, user_id)
            )
            
            # Get updated total
            cur.execute(
                "SELECT total_xp FROM users WHERE id = %s::uuid",
                (user_id,)
            )
            total_xp = cur.fetchone()[0]
            
            conn.commit()
            
            return {
                "user_id": user_id,
                "total_xp": total_xp,
                "new_xp": amount,
                "action": action
            }
        finally:
            conn.close()
    
    def get_xp_history(self, user_id: str, limit: int = 50, offset: int = 0):
        """Get XP history for a user."""
        # Implementation here
        pass
    
    def daily_login_bonus(self, user_id: str) -> dict:
        """Check if user already got daily bonus today."""
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            
            # Check if LoginDaily action exists for today
            cur.execute(
                """SELECT COUNT(*) FROM xp_events
                   WHERE user_id = %s::uuid
                   AND action = 'LoginDaily'
                   AND DATE(created_at) = CURRENT_DATE""",
                (user_id,)
            )
            
            if cur.fetchone()[0] == 0:
                # Award daily login XP
                return self.log_xp(user_id, "LoginDaily", 5)
            else:
                return {"status": "already_claimed"}
        finally:
            conn.close()
```

#### Integration Points

**In `/api/submit-evidence` (main.py):**
```python
# After evidence submitted, award XP
xp_manager = XPManager()
xp_manager.log_xp(user_id, "MissionSubmitted", 50)
```

**In `/api/awards/{award_id}/collect` (main.py):**
```python
# Determine tier and award XP
tier_xp = {
    "common": 50,
    "epic": 100,
    "legendary": 150
}
xp_manager.log_xp(user_id, "MissionCompleted", tier_xp[tier], 
                   context={"mission_id": mission_id, "tier": tier})
```

**In `/api/dev-login` (main.py):**
```python
# Award daily login bonus
xp_manager.daily_login_bonus(user_id)
```

### Testing

```python
def test_xp_logging():
    xp_mgr = XPManager()
    
    # Log XP
    result = xp_mgr.log_xp("user-1", "MissionCompleted", 100)
    assert result["total_xp"] == 100
    
    # Log more XP
    result = xp_mgr.log_xp("user-1", "LoginDaily", 5)
    assert result["total_xp"] == 105
    
    # Verify immutability
    result = xp_mgr.log_xp("user-1", "MissionCompleted", 100)
    assert result["total_xp"] == 205
    # XP is never removed

def test_daily_login_bonus():
    xp_mgr = XPManager()
    
    # First login today
    result = xp_mgr.daily_login_bonus("user-1")
    assert result["new_xp"] == 5
    
    # Second login today
    result = xp_mgr.daily_login_bonus("user-1")
    assert result["status"] == "already_claimed"
```

### UI Updates

**Dashboard (index.html):**
Add XP counter to header:
```html
<div class="xp-badge">
  <span id="totalXP">0</span> XP
</div>

<script>
async function loadXP() {
  const response = await fetch(`/api/xp/${currentUserId}`);
  const data = await response.json();
  document.getElementById('totalXP').textContent = data.total_xp;
}
</script>
```

**After Evidence Submission:**
Show XP reward popup:
```html
<div class="xp-popup">
  <p>Mission Submitted!</p>
  <p class="xp-amount">+50 XP</p>
</div>
```

### Acceptance Criteria

- [ ] XP increments correctly per action
- [ ] Total XP never decreases
- [ ] Daily login bonus only awarded once per day
- [ ] XP history accessible via API
- [ ] Dashboard shows current XP balance
- [ ] XP awarded event shows in timeline

---

## 2. Levels System (1 week)

### Database Schema

Add to `users` table:
```sql
ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1;
```

### Level Formula

Simple exponential progression:
```
level = 1 + floor(log10(xp / 100 + 1) / log10(1.5))
```

Or pre-computed thresholds:

| Level | XP Required |
|-------|-------------|
| 1 | 0 |
| 2 | 100 |
| 3 | 225 |
| 4 | 391 |
| 5 | 605 |
| 6 | 878 |
| 7 | 1216 |
| 8 | 1632 |
| 9 | 2138 |
| 10 | 2744 |
| 11 | 3470 |
| 12 | 4335 |
| 13 | 5365 |
| 14 | 6590 |
| 15 | 8036 |
| 16 | 9742 |
| 17 | 11743 |
| 18 | 14091 |
| 19 | 16844 |
| 20 | 20062 |

Level 20 = "Master Problem Solver"

### Create Levels Table

```sql
CREATE TABLE levels (
    level INTEGER PRIMARY KEY,
    xp_required INTEGER NOT NULL,
    title VARCHAR(255),
    description TEXT
);

-- Seed data
INSERT INTO levels (level, xp_required, title, description) VALUES
(1, 0, 'Explorer', 'Just starting your journey'),
(2, 100, 'Investigator', 'Completed first mission'),
(3, 225, 'Researcher', 'Gathering knowledge'),
...
(20, 20062, 'Master Problem Solver', 'Reached the summit');
```

### Events

Create new event: `LevelUp`

```python
# Event published when XP crosses threshold
{
  "event_type": "LevelUp",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "user_id": "uuid",
    "new_level": 5,
    "previous_level": 4,
    "total_xp": 605
  }
}
```

### API Endpoints

```
GET /api/users/{user_id}/level

Response:
{
  "current_level": 5,
  "current_xp": 605,
  "xp_for_next_level": 878,
  "xp_until_next_level": 273,
  "progress_percent": 69,
  "title": "Researcher"
}
```

### Implementation

#### File: `evoke/levels.py` (new)

```python
import json

class LevelManager:
    LEVEL_THRESHOLDS = {
        1: 0, 2: 100, 3: 225, 4: 391, 5: 605,
        6: 878, 7: 1216, 8: 1632, 9: 2138, 10: 2744,
        # ... up to 20
    }
    
    def calculate_level(self, total_xp: int) -> int:
        """Calculate level from total XP."""
        for level in range(20, 0, -1):
            if total_xp >= self.LEVEL_THRESHOLDS[level]:
                return level
        return 1
    
    def get_level_info(self, user_id: str) -> dict:
        """Get user's level and progress."""
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT total_xp, level FROM users WHERE id = %s::uuid",
                (user_id,)
            )
            total_xp, current_level = cur.fetchone()
            
            next_level = min(current_level + 1, 20)
            xp_for_next = self.LEVEL_THRESHOLDS[next_level]
            xp_until_next = max(0, xp_for_next - total_xp)
            
            return {
                "current_level": current_level,
                "current_xp": total_xp,
                "xp_for_next_level": xp_for_next,
                "xp_until_next_level": xp_until_next,
                "progress_percent": int((total_xp - self.LEVEL_THRESHOLDS[current_level]) / 
                                        (xp_for_next - self.LEVEL_THRESHOLDS[current_level]) * 100)
            }
        finally:
            conn.close()
    
    def check_level_up(self, user_id: str, old_xp: int, new_xp: int):
        """Check if user leveled up and publish event."""
        old_level = self.calculate_level(old_xp)
        new_level = self.calculate_level(new_xp)
        
        if new_level > old_level:
            # Update user level
            conn = get_db_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE users SET level = %s WHERE id = %s::uuid",
                    (new_level, user_id)
                )
                conn.commit()
            finally:
                conn.close()
            
            # Publish event
            return {
                "event_type": "LevelUp",
                "user_id": user_id,
                "new_level": new_level,
                "previous_level": old_level,
                "total_xp": new_xp
            }
        return None
```

#### Integration

Modify `XPManager.log_xp()` to check for level up:

```python
def log_xp(self, user_id: str, action: str, amount: int, context: dict = None):
    # ... existing XP logic ...
    old_xp = current_xp - amount  # XP before this action
    
    level_mgr = LevelManager()
    level_up_event = level_mgr.check_level_up(user_id, old_xp, total_xp)
    
    if level_up_event:
        # Publish LevelUp event
        await publish_event(level_up_event)
        # Award level-up bonus XP (optional)
        self.log_xp(user_id, "LevelUp", 0, context={"level": level_up_event["new_level"]})
    
    return result
```

### UI Updates

**Level Badge (header):**
```html
<div class="level-badge">
  <span id="userLevel">1</span>
</div>

<script>
async function loadLevel() {
  const response = await fetch(`/api/users/${currentUserId}/level`);
  const data = await response.json();
  document.getElementById('userLevel').textContent = data.current_level;
}
</script>
```

**Level Up Celebration:**
```html
<div class="level-up-modal" id="levelUpModal">
  <h2>Level Up! 🎉</h2>
  <p>You reached <strong id="newLevel">5</strong></p>
  <p id="levelTitle">Researcher</p>
  <button onclick="closeLevelUp()">Continue</button>
</div>

<script>
// When LevelUp event received (via WebSocket or polling)
function showLevelUp(event) {
  document.getElementById('newLevel').textContent = event.new_level;
  document.getElementById('levelUpModal').style.display = 'block';
}
</script>
```

### Acceptance Criteria

- [ ] Level calculated correctly from XP
- [ ] Level increments only when crossing threshold
- [ ] LevelUp event published to Redpanda
- [ ] Celebration UI shows when level up occurs
- [ ] Level displayed on all UI surfaces
- [ ] No "level down" ever occurs

---

## 3. Superpower Progress (1 week)

### Database Schema

Enhance `missions` table:

```sql
-- Already has: superpower VARCHAR(100)
-- Example values: 'Empathetic Changemaker', 'Systems Thinker', etc.
```

Create tracking table:

```sql
CREATE TABLE superpower_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    superpower_name VARCHAR(100) NOT NULL,
    progress_percent INTEGER DEFAULT 0,  -- 0-100
    missions_completed INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, superpower_name)
);

CREATE INDEX idx_superpower_progress_user ON superpower_progress(user_id);
```

### Events

Create new event: `SuperpowerProgressed`

```python
{
  "event_type": "SuperpowerProgressed",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "user_id": "uuid",
    "superpower": "Systems Thinker",
    "progress_percent": 50,
    "missions_completed": 2,
    "next_milestone": 75
  }
}
```

And: `SuperpowerMastered`

```python
{
  "event_type": "SuperpowerMastered",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "user_id": "uuid",
    "superpower": "Systems Thinker"
  }
}
```

### API Endpoints

```
GET /api/superpowers/{user_id}

Response:
{
  "superpowers": [
    {
      "name": "Systems Thinker",
      "progress_percent": 50,
      "missions_completed": 2,
      "mastered": false,
      "next_milestone": 75
    },
    {
      "name": "Empathetic Changemaker",
      "progress_percent": 25,
      "missions_completed": 1,
      "mastered": false,
      "next_milestone": 50
    },
    ...
  ]
}
```

### Implementation

#### File: `evoke/superpowers.py` (new)

```python
class SuperpowerManager:
    # 4 superpowers, each earned through missions
    SUPERPOWERS = [
        "Empathetic Changemaker",
        "Systems Thinker",
        "Creative Visionary",
        "Deep Collaborator"
    ]
    
    # Milestone percentages
    MILESTONES = [25, 50, 75, 100]
    
    def update_progress(self, user_id: str, superpower: str, mission_completed: bool):
        """Update superpower progress when mission completed."""
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            
            # Get or create progress record
            cur.execute(
                """INSERT INTO superpower_progress (user_id, superpower_name)
                   VALUES (%s::uuid, %s)
                   ON CONFLICT (user_id, superpower_name) DO NOTHING""",
                (user_id, superpower)
            )
            
            # Calculate progress (1 mission = 25%)
            cur.execute(
                """UPDATE superpower_progress
                   SET missions_completed = missions_completed + 1,
                       progress_percent = LEAST(100, missions_completed * 25)
                   WHERE user_id = %s::uuid AND superpower_name = %s""",
                (user_id, superpower)
            )
            
            # Get updated progress
            cur.execute(
                """SELECT progress_percent, missions_completed
                   FROM superpower_progress
                   WHERE user_id = %s::uuid AND superpower_name = %s""",
                (user_id, superpower)
            )
            progress, missions = cur.fetchone()
            
            conn.commit()
            
            # Check for milestone/mastery
            event = None
            if progress < 100:
                event = {
                    "event_type": "SuperpowerProgressed",
                    "data": {
                        "user_id": user_id,
                        "superpower": superpower,
                        "progress_percent": progress,
                        "missions_completed": missions
                    }
                }
            elif progress == 100:
                event = {
                    "event_type": "SuperpowerMastered",
                    "data": {
                        "user_id": user_id,
                        "superpower": superpower
                    }
                }
            
            return event
        finally:
            conn.close()
    
    def get_progress(self, user_id: str):
        """Get superpower progress for user."""
        # Implementation here
        pass
```

#### Integration

In `evoke/main.py`, when mission completed:

```python
# After awards created
mission = db_fetch_one("SELECT superpower FROM missions WHERE id = %s::uuid", (mission_id,))
if mission:
    sp_mgr = SuperpowerManager()
    event = sp_mgr.update_progress(user_id, mission[0], True)
    if event:
        await publish_event(event)
```

### UI Updates

**Progress Bars (dashboard):**
```html
<div class="superpowers">
  <h3>Your Superpowers</h3>
  <div id="superpowersList"></div>
</div>

<script>
async function loadSuperpowers() {
  const response = await fetch(`/api/superpowers/${currentUserId}`);
  const data = await response.json();
  
  document.getElementById('superpowersList').innerHTML = 
    data.superpowers.map(sp => `
      <div class="superpower-bar">
        <div class="label">${sp.name}</div>
        <div class="progress-bar">
          <div class="progress" style="width: ${sp.progress_percent}%"></div>
        </div>
        <div class="milestone">${sp.progress_percent}% • ${sp.missions_completed} missions</div>
      </div>
    `).join('');
}
</script>
```

### Acceptance Criteria

- [ ] Progress tracked for all 4 superpowers
- [ ] Progress increments 25% per mission
- [ ] Events published at milestones
- [ ] Progress bars display on dashboard
- [ ] Mastery event triggers badge award (Phase 3)

---

## 4. Achievement Badges (2 weeks)

### Database Schema

Create achievement definitions:

```sql
CREATE TABLE achievement_badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(100) UNIQUE NOT NULL,  -- e.g., "explorer"
    name VARCHAR(255) NOT NULL,
    description TEXT,
    icon_url VARCHAR(500),
    category VARCHAR(50),  -- story, learning, teamwork, community, creativity, hidden
    rarity VARCHAR(50)     -- common, rare, legendary
);

CREATE TABLE user_achievements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    achievement_id UUID NOT NULL REFERENCES achievement_badges(id),
    awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, achievement_id)
);

CREATE INDEX idx_user_achievements_user ON user_achievements(user_id);
```

Seed initial achievements:

```sql
INSERT INTO achievement_badges (key, name, description, category, rarity) VALUES
-- Story
('explorer', 'Explorer', 'Started the journey', 'story', 'common'),
('survivor', 'Survivor', 'Completed 5 missions', 'story', 'rare'),
('innovator', 'Innovator', 'Reached level 10', 'story', 'rare'),
('builder', 'Builder', 'Completed 10 missions', 'story', 'rare'),
('entrepreneur', 'Entrepreneur', 'Started a team venture', 'story', 'legendary'),

-- Learning
('research_expert', 'Research Expert', 'Earned Researcher level', 'learning', 'rare'),
('interview_master', 'Interview Master', 'Completed 3 community investigations', 'learning', 'rare'),
('prototype_builder', 'Prototype Builder', 'Built and submitted 5 prototypes', 'learning', 'rare'),
('critical_thinker', 'Critical Thinker', 'Mastered Systems Thinker superpower', 'learning', 'legendary'),
('evidence_collector', 'Evidence Collector', 'Submitted 20 pieces of evidence', 'learning', 'rare'),

-- Teamwork
('reliable_teammate', 'Reliable Teammate', 'Never missed a team deadline', 'teamwork', 'rare'),
('mentor', 'Mentor', 'Helped 5 teammates', 'teamwork', 'rare'),
('leadership', 'Leadership', 'Led a successful team project', 'teamwork', 'legendary'),
('problem_solver', 'Problem Solver', 'Overcame 3 mission challenges', 'teamwork', 'rare'),
('consensus_builder', 'Consensus Builder', 'Facilitated team decisions', 'teamwork', 'rare'),

-- Community
('volunteer', 'Volunteer', 'Helped 1 person outside class', 'community', 'common'),
('community_impact', 'Community Impact', 'Completed 3 community projects', 'community', 'rare'),
('local_hero', 'Local Hero', 'Earned 5 community badges', 'community', 'rare'),
('changemaker', 'Changemaker', 'Mastered Empathetic Changemaker superpower', 'community', 'legendary'),

-- Creativity
('inventor', 'Inventor', 'Designed 5 unique solutions', 'creativity', 'rare'),
('designer', 'Designer', 'Created visual prototypes', 'creativity', 'rare'),
('artist', 'Artist', 'Submitted artistic evidence', 'creativity', 'rare'),
('engineer', 'Engineer', 'Built technical solutions', 'creativity', 'rare'),

-- Hidden
('speedrunner', 'Speedrunner', 'Completed mission in <1 day', 'hidden', 'legendary'),
('perfectionist', 'Perfectionist', 'Got all legendary awards on one mission', 'hidden', 'legendary'),
('obsessed', 'Obsessed', 'Spent 10+ hours in Minecraft for quests', 'hidden', 'rare');
```

### Unlock Rules

Create a rules engine:

```sql
CREATE TABLE achievement_unlock_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    achievement_id UUID NOT NULL REFERENCES achievement_badges(id),
    rule_type VARCHAR(50),  -- "level_reach", "mission_count", "xp_threshold", 
                             -- "streak_days", "feedback_count", "superpower_mastery", "team_size"
    rule_value INTEGER,      -- threshold/count
    UNIQUE(achievement_id, rule_type)
);

INSERT INTO achievement_unlock_rules (achievement_id, rule_type, rule_value) 
SELECT id, 'level_reach', 2 FROM achievement_badges WHERE key = 'explorer';

INSERT INTO achievement_unlock_rules (achievement_id, rule_type, rule_value) 
SELECT id, 'mission_count', 5 FROM achievement_badges WHERE key = 'survivor';

INSERT INTO achievement_unlock_rules (achievement_id, rule_type, rule_value) 
SELECT id, 'level_reach', 10 FROM achievement_badges WHERE key = 'innovator';

-- ... etc for all achievements
```

### Events

Create new event: `AchievementUnlocked`

```python
{
  "event_type": "AchievementUnlocked",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "user_id": "uuid",
    "achievement_key": "explorer",
    "achievement_name": "Explorer",
    "rarity": "common"
  }
}
```

### API Endpoints

```
GET /api/achievements/{user_id}

Response:
{
  "earned": [
    {
      "key": "explorer",
      "name": "Explorer",
      "icon_url": "...",
      "awarded_at": "2024-01-15T10:30:00Z",
      "rarity": "common"
    },
    ...
  ],
  "progress": [
    {
      "key": "survivor",
      "name": "Survivor",
      "progress": 2,  // 2 out of 5 missions
      "required": 5
    },
    ...
  ]
}
```

### Implementation

#### File: `evoke/achievements.py` (new)

```python
class AchievementManager:
    def check_unlocks(self, user_id: str, trigger_type: str, trigger_value: int):
        """Check if any achievements should unlock based on event."""
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            
            # Get all rules matching this trigger
            cur.execute(
                """SELECT ab.id, ab.key, ab.name, ab.rarity
                   FROM achievement_unlock_rules aur
                   JOIN achievement_badges ab ON aur.achievement_id = ab.id
                   WHERE aur.rule_type = %s AND aur.rule_value <= %s""",
                (trigger_type, trigger_value)
            )
            
            unlocks = cur.fetchall()
            unlocked_achievements = []
            
            for achievement_id, key, name, rarity in unlocks:
                # Check if already earned
                cur.execute(
                    """SELECT id FROM user_achievements
                       WHERE user_id = %s::uuid AND achievement_id = %s::uuid""",
                    (user_id, achievement_id)
                )
                
                if not cur.fetchone():
                    # Award achievement
                    cur.execute(
                        """INSERT INTO user_achievements (user_id, achievement_id)
                           VALUES (%s::uuid, %s::uuid)""",
                        (user_id, achievement_id)
                    )
                    conn.commit()
                    
                    unlocked_achievements.append({
                        "event_type": "AchievementUnlocked",
                        "data": {
                            "user_id": user_id,
                            "achievement_key": key,
                            "achievement_name": name,
                            "rarity": rarity
                        }
                    })
            
            return unlocked_achievements
        finally:
            conn.close()
```

#### Integration

Hook into existing event pipeline:

```python
# In workers.py, new achievement worker
async def achievement_worker():
    """Listen for events that trigger achievement checks."""
    consumer = KafkaConsumer(
        'evoke-events',
        bootstrap_servers=['redpanda:29092'],
        group_id='achievement-worker'
    )
    
    for message in consumer:
        event = json.loads(message.value)
        user_id = event['data'].get('user_id')
        
        if event['event_type'] == 'LevelUp':
            new_level = event['data']['new_level']
            achievement_mgr = AchievementManager()
            unlocks = achievement_mgr.check_unlocks(
                user_id, "level_reach", new_level
            )
            for unlock_event in unlocks:
                producer.send('evoke-events', value=unlock_event)
        
        elif event['event_type'] == 'MissionCompleted':
            achievement_mgr = AchievementManager()
            # Check mission_count rule
            cur.execute(
                "SELECT COUNT(*) FROM awards WHERE user_id = %s::uuid AND collected_at IS NOT NULL",
                (user_id,)
            )
            mission_count = cur.fetchone()[0]
            unlocks = achievement_mgr.check_unlocks(
                user_id, "mission_count", mission_count
            )
            for unlock_event in unlocks:
                producer.send('evoke-events', value=unlock_event)
```

### UI Updates

**Achievement Grid (profile):**
```html
<div class="achievements">
  <h3>Achievements Earned</h3>
  <div class="achievement-grid" id="achievementsList"></div>
</div>

<script>
async function loadAchievements() {
  const response = await fetch(`/api/achievements/${currentUserId}`);
  const data = await response.json();
  
  document.getElementById('achievementsList').innerHTML = 
    data.earned.map(ach => `
      <div class="achievement-badge ${ach.rarity}">
        <img src="${ach.icon_url}" alt="${ach.name}">
        <div class="name">${ach.name}</div>
        <div class="date">${new Date(ach.awarded_at).toLocaleDateString()}</div>
      </div>
    `).join('');
}
</script>
```

**Achievement Unlock Toast:**
```html
<div class="achievement-toast" id="achievementToast">
  <img id="achievementIcon" src="">
  <div class="content">
    <h4>Achievement Unlocked!</h4>
    <p id="achievementName"></p>
  </div>
</div>

<script>
// Show when event received
function showAchievementUnlock(event) {
  document.getElementById('achievementIcon').src = event.icon_url;
  document.getElementById('achievementName').textContent = event.achievement_name;
  document.getElementById('achievementToast').style.display = 'block';
  setTimeout(() => {
    document.getElementById('achievementToast').style.display = 'none';
  }, 5000);
}
</script>
```

### Acceptance Criteria

- [ ] All 20+ achievements defined and seeded
- [ ] Unlock rules configured and tested
- [ ] Events published on achievement unlock
- [ ] Achievement grid shows on profile
- [ ] Toast notification on unlock
- [ ] Progress displayed for locked achievements

---

## Testing Strategy

### Unit Tests (by component)

**XP Tests:**
```python
def test_xp_increments()
def test_xp_never_decreases()
def test_daily_login_single_per_day()
def test_xp_logging_with_context()
```

**Level Tests:**
```python
def test_level_calculated_from_xp()
def test_level_only_increments()
def test_level_up_event_published()
def test_all_thresholds_correct()
```

**Superpower Tests:**
```python
def test_progress_increments_per_mission()
def test_progress_capped_at_100()
def test_mastery_event_published_at_100()
def test_all_superpowers_trackable()
```

**Achievement Tests:**
```python
def test_achievement_unlock_on_rule_match()
def test_achievement_only_earned_once()
def test_event_published_on_unlock()
def test_locked_achievements_show_progress()
```

### Integration Tests

```python
def test_full_mission_flow():
    """Submit evidence → XP awarded → level up → achievement unlocked."""
    # Setup
    user_id = "test-user"
    
    # Submit evidence
    submit_evidence(user_id, mission_id="m1")
    
    # Assert: XP awarded
    xp_history = get_xp_history(user_id)
    assert xp_history[0]['action'] == 'MissionSubmitted'
    assert xp_history[0]['amount'] == 50
    
    # Assert: Timeline shows XP event
    timeline = get_timeline(user_id)
    assert any(e['type'] == 'XPGranted' for e in timeline)
    
    # Assert: Dashboard shows XP
    dashboard = get_dashboard(user_id)
    assert dashboard['total_xp'] == 50
```

### End-to-End (UI) Tests

```gherkin
Feature: XP and Progression
  
  Scenario: Learner earns XP on submission
    Given I'm logged in as a learner
    When I submit evidence to Mission 1
    Then I see "+50 XP" notification
    And my dashboard XP increases to 50
    
  Scenario: Level up triggers celebration
    Given I have 95 XP (level 2)
    When I submit evidence earning +10 XP
    Then I see "Level Up! 🎉" modal
    And my level becomes 3
    And a new superpower appears on dashboard
    
  Scenario: Achievement unlocks on milestone
    Given I have earned 5 missions (50%)
    When I complete my 5th mission
    Then "Survivor" achievement appears
    And I see achievement unlock toast
    And achievement appears on profile
```

---

## Rollout Checklist

### Pre-Launch (Week 4)
- [ ] Database migrations tested on copy of production schema
- [ ] Unit tests pass (>95% coverage)
- [ ] Integration tests pass
- [ ] UI mockups approved by stakeholders
- [ ] Performance testing done (XP queries <100ms)
- [ ] Documentation written

### Launch Day (Week 5)
- [ ] Feature flag ready (can disable if issues)
- [ ] Alerts configured (monitor error rates)
- [ ] Dashboard ready to show team progress
- [ ] Stakeholder comms prepared
- [ ] Rollback plan documented

### Post-Launch (Week 5)
- [ ] Monitor error logs for first 24 hours
- [ ] Gather feedback from beta learners
- [ ] Tweak XP values based on playtesting
- [ ] Prepare for Phase 2 kickoff

---

## Success Metrics

**Technical:**
- XP awarded correctly 100% of time
- Level recalculation <1s
- Badges unlock automatically
- Zero data corruption

**User Engagement:**
- Avg XP per learner: 200+/week
- Level-up frequency: 1-2 times per week
- Achievement unlock rate: 3+ per learner (first 2 weeks)
- Dashboard visits increase 50%+

**Feedback:**
- "I feel like I'm progressing" — 80%+ agreement
- "The XP system feels fair" — 75%+ agreement
- "I want to level up faster" — drives healthy engagement

---

## Known Unknowns & Decisions

1. **XP Balance**: Are the values too high/low? First cohort will tell us. Adjust via config if needed.
2. **Level Difficulty**: Is level 20 too hard to reach? Consider exponential easing if dropout high.
3. **Achievement Rarity**: Are legendary achievements too rare? Feedback from beta.
4. **Daily Login Bonus**: Should this be in Phase 1 or Phase 7? Recommend Phase 1 (simple).

---

## Links & Resources

- ROLLOUT_PLAN.md — Full roadmap
- ROLLOUT_VISUAL.md — Visual timeline
- ARCHITECTURE.md — System design
- DATABASE schema: `evoke-infra/init-db.sql`
- Existing MVP: `BUILD_SUMMARY.md`

---

## Next Phase

Upon Phase 1 completion, immediately start Phase 2 (Timeline & Portfolio). Many dependencies are ready:
- XP events feed the timeline
- Levels unlock story pages (Phase 5)
- Achievements feed profile page (Phase 2)
