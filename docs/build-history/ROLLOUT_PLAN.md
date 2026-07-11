# EVOKE Prosperity - Feature Rollout Plan

Based on `CONCEPTS.md`, `ARCHITECTURE.md`, `BUILD_PROMPT.md`, and the product vision in `docs/canon/overview.md`, this document outlines the complete rollout strategy from MVP (complete) to production-ready platform.

## Current State (MVP Complete ✅)

**Core infrastructure & demo flow:**
- ✅ Event-driven architecture (Redpanda)
- ✅ PostgreSQL schema (campaigns, missions, users, awards, Minecraft)
- ✅ 12-mission curriculum seeded
- ✅ Award pipeline (submission → AI → teacher → collect → deliver)
- ✅ Minecraft reward delivery via RCON
- ✅ Two UIs (Operations Hub + Companion Mode)
- ✅ B1llbot AI integration
- ✅ Simulated Brightspace LMS

**Not in MVP:**
- XP / Levels / Badges (progression mechanics)
- Streaks (daily engagement)
- Portfolio / Vault
- Profile page
- Timeline view (learner journey)
- Team collaboration
- Instructor dashboard
- Search
- Reflections
- Real LMS integration (Brightspace/Moodle)
- Story integration (lore pages unlock with progress)
- Polished UI (still wireframe)

---

## Phase 1: Core Progression Mechanics (4-6 weeks)

**Goal:** Add XP/Levels/Badges system so learners see continuous progression

### Features

#### 1.1 XP System
**Scope:** Track XP, never remove, expose in all UIs

- Add `xp` column to `users` table
- New table: `xp_events` (user_id, action, amount, timestamp)
- Event types: `LoginDaily`, `MissionCompleted`, `QuestCompleted`, `HelpedTeammate`, `ReceivedFeedback`, `ReflectionAdded`
- Endpoint: `POST /api/xp/{user_id}/log` (internal, workers call this)
- Timeline display: show XP gains as events
- UI: Dashboard XP counter, mission completion shows XP earned

**Payload Example:**
```json
{
  "user_id": "...",
  "action": "MissionCompleted",
  "amount": 100,
  "context": { "mission_id": "...", "tier": "epic" }
}
```

**Time estimate:** 1 week
- Schema: 1 day
- Worker: 2 days (integrate with existing award flow)
- API: 2 days
- UI updates: 2 days

---

#### 1.2 Levels
**Scope:** Exponential XP → Level progression (1-20)

- Add `level` column to `users`
- Level formula: `level = 1 + floor(log(xp / 100) / log(1.5))`
- Event: `LevelUp` (published when XP crosses threshold)
- Endpoints:
  - `GET /api/users/{user_id}/level` - current level + next milestone
  - `POST /api/levels/recalculate` (admin, for backfill)
- UI: Level indicator on dashboard, celebration animation on level up
- Unlock mechanism: missions/quests/story chapters can require minimum level

**Time estimate:** 1 week
- Schema: 1 day
- Level calculation: 2 days
- Event publishing: 2 days
- UI: 2 days

---

#### 1.3 Superpower Badges (Existing, but enhance)
**Scope:** Track superpower progress, show tier progress

Currently: 4 superpowers (Empathetic Changemaker, Systems Thinker, Creative Visionary, Deep Collaborator)

Changes needed:
- Each mission awards progress toward one superpower (already in schema)
- Track progression: 0-25%-50%-75%-100% (add `progress` column to `badges` table or use separate table)
- Event: `SuperpowerProgressed` (on each mission completion)
- Badge unlock: at 100%, award the badge
- UI: Superpower progress bars on dashboard
- Endpoint: `GET /api/superpowers/{user_id}`

**Time estimate:** 1 week
- Schema: 1 day
- Progress tracking: 2 days
- Event publishing: 1 day
- UI: 2 days

---

#### 1.4 Achievement Badges (20+)
**Scope:** Unlock special badges for notable events

Categories (from `docs/canon/overview.md`):
- Story (Explorer, Survivor, Innovator, Builder, Entrepreneur)
- Learning (Research Expert, Interview Master, Prototype Builder, Critical Thinker, Evidence Collector)
- Teamwork (Reliable Teammate, Mentor, Leadership, Problem Solver, Consensus Builder)
- Community (Volunteer, Community Impact, Local Hero, Changemaker)
- Creativity (Inventor, Designer, Artist, Engineer)
- Hidden/Secret (discovered through gameplay)

Implementation:
- New table: `achievement_rules` (badge_id, trigger_type, trigger_value)
- Trigger types: "mission_count", "xp_threshold", "team_size", "feedback_count", "quest_count", "perfect_attendance"
- Worker: Listen for events, check rules, award badges
- Endpoint: `GET /api/badges/{user_id}`
- UI: Badge showcase on profile/dashboard

**Time estimate:** 2 weeks
- Schema: 2 days
- Rules engine: 4 days
- 20+ badge definitions: 3 days
- Worker integration: 3 days
- UI: 3 days

---

### Phase 1 Acceptance Criteria

- [ ] XP counter shows on dashboard after mission submission
- [ ] Learner levels up when XP crosses threshold
- [ ] Achievement badges unlock as learner progresses
- [ ] Timeline shows XP gains and level ups
- [ ] Superpower progress bars visible
- [ ] No XP ever removed (idempotency tested)

---

## Phase 2: Timeline & Portfolio (4-6 weeks)

**Goal:** Show learner's journey and persistent record of all work

### Features

#### 2.1 Timeline View
**Scope:** Per-learner journey showing all progress

From `overview.md` section 18:
```
Mission Started → Evidence Uploaded → AI Feedback → Teacher Feedback → 
Revision → Badge Earned → Mission Complete → Level Up → Unlocked Story
```

Implementation:
- Read from OpenSearch `learner-timeline` index (already projected by workers)
- Timeline events: mission start, evidence submit, feedback add, badge award, level up, story unlock
- Endpoint: `GET /api/timeline/{user_id}?limit=50&offset=0` (paginated)
- UI: Vertical timeline card layout, newest at top
- Features:
  - Timeline cards for each event (different styling per event type)
  - Click to expand (show evidence, full feedback, etc.)
  - Filter by event type (missions only, badges only, etc.)

**Time estimate:** 2 weeks
- OpenSearch projection refinement: 3 days
- API endpoint: 3 days
- UI (timeline cards): 5 days
- Testing: 2 days

---

#### 2.2 Profile Page
**Scope:** Learner showcase of identity, progress, skills

From `overview.md` section 5:

Sections:
1. Identity: Avatar, name, organization, level, rank, current XP
2. Progress: Current mission, completed count, story progress %
3. Skills: Radar chart showing 8 key skills (empathy, research, communication, entrepreneurship, leadership, creativity, systems thinking, financial literacy)
   - Skills inferred from badge/mission completion
4. Achievements: Grid of all earned badges
5. Team affiliations (if in team)

Implementation:
- New table: `learner_skills` (user_id, skill_name, score 0-100)
- Skill calculation: aggregate from badge categories
- Endpoint: `GET /api/users/{user_id}/profile`
- UI: Profile card layout with tabs for each section
- Feature: "Share profile" → generate static link (read-only public profile)

**Time estimate:** 2 weeks
- Schema: 1 day
- Skill calculation: 3 days
- API: 2 days
- UI: 5 days
- Public profile link: 2 days

---

#### 2.3 Portfolio / Vault
**Scope:** Persistent collection of all submissions and evidence

From `overview.md` section 24:

Features:
- All submitted evidence (files, photos, videos)
- Instructor + AI feedback (never removed)
- Reflections (see 2.4 below)
- Certificates (generated on mission completion)
- Organized by mission/date/type

Implementation:
- Already storing files in MinIO per mission
- Portfolio index in OpenSearch: mission_id, user_id, submission_date, file_type, feedback
- Endpoint: `GET /api/portfolio/{user_id}?filter=missions|quests|feedback` (paginated)
- UI: Gallery/list view of portfolio items, click to view full evidence + feedback
- Feature: Export portfolio as PDF/document

**Time estimate:** 2 weeks
- OpenSearch index: 2 days
- API endpoint: 2 days
- UI (gallery): 4 days
- Export to PDF: 3 days
- Testing: 2 days

---

#### 2.4 Reflections
**Scope:** Learners record structured reflections on missions

From `overview.md`:
- Reflection after evidence submission
- XP reward: +15 per reflection
- Part of portfolio

Implementation:
- New table: `reflections` (user_id, mission_id, text, submitted_at)
- Prompts per mission type (e.g., "What did you learn? What was challenging?")
- Endpoint: `POST /api/reflections`, `GET /api/reflections/{user_id}`
- Event: `ReflectionAdded` → triggers +15 XP, adds to timeline
- UI: Modal/form after mission submission asking for reflection
- Reflection view in portfolio/timeline

**Time estimate:** 1 week
- Schema: 1 day
- API: 2 days
- Event publishing: 1 day
- UI (form + display): 2 days

---

### Phase 2 Acceptance Criteria

- [ ] Learner sees full timeline of progress (missions, feedback, badges, level ups)
- [ ] Profile page shows identity, skills radar, achievements, team
- [ ] Portfolio displays all submitted evidence with feedback
- [ ] Reflections can be added after missions
- [ ] Timeline/Portfolio integrated with existing award system
- [ ] OpenSearch indexes are real-time updated

---

## Phase 3: Team Collaboration (3-4 weeks)

**Goal:** Enable small teams (4-person squads) to work together

### Features

#### 3.1 Team Management
**Scope:** Create/join teams, assign roles

Implementation:
- Enhance existing `teams` table
- Add: logo, description, preferred_name
- Endpoints:
  - `POST /api/teams` - create
  - `GET /api/teams/{team_id}` - view
  - `POST /api/teams/{team_id}/members` - add member
  - `DELETE /api/teams/{team_id}/members/{user_id}` - remove member
  - `PUT /api/teams/{team_id}/members/{user_id}/role` - set role (Leader, Researcher, Builder, Designer, Presenter, Recorder, Community Liaison, Developer)
- Events: `TeamCreated`, `TeamMemberAdded`, `TeamMemberRemoved`, `RoleAssigned`
- UI: Team creation wizard, team settings, member management

**Time estimate:** 1.5 weeks
- Schema/enhance: 1 day
- API endpoints: 3 days
- Events & workers: 2 days
- UI (team management): 3 days

---

#### 3.2 Team Submissions
**Scope:** Teams submit evidence together

Implementation:
- Modify evidence submission to support team_id in addition to user_id
- Team evidence still goes to Brightspace but attributed to team
- Awards granted to all team members
- XP split or multiplied per mission design (TBD)

**Time estimate:** 1 week
- API changes: 2 days
- Brightspace sync: 2 days
- Award distribution logic: 2 days
- Testing: 1 day

---

#### 3.3 Team Timeline & Shared Progress
**Scope:** Team view of collective work

Implementation:
- Team profile page similar to learner profile
- Team timeline: combined events from all members
- Team badges: unlocked when all members earn badge or team XP threshold
- Endpoint: `GET /api/teams/{team_id}/profile`, `GET /api/teams/{team_id}/timeline`
- UI: Team page with shared achievements, member contributions, timeline

**Time estimate:** 1 week
- Schema for team badges: 1 day
- API: 2 days
- UI (team page): 3 days

---

#### 3.4 Peer Recognition
**Scope:** Team members recognize each other

Implementation:
- New table: `peer_recognition` (from_user, to_user, team_id, message, timestamp)
- Triggers: +20 XP to recognized user
- UI: "Shout out" feature on team page
- Dashboard: show recent peer recognition

**Time estimate:** 1 week (low priority, can defer)

---

### Phase 3 Acceptance Criteria

- [ ] Teams can be created and configured
- [ ] Members can join/leave teams
- [ ] Teams submit evidence together
- [ ] Team timeline shows collective progress
- [ ] Team badges unlock appropriately
- [ ] All team members receive XP for team submissions

---

## Phase 4: Instructor Experience (3-4 weeks)

**Goal:** Teachers can review progress, provide feedback, monitor engagement

### Features

#### 4.1 Instructor Dashboard
**Scope:** High-level view of class progress

From `overview.md` section 22:

Views:
1. Class overview: Total students, current mission distribution, average level, engagement %
2. Student list: Each student with current mission, XP, level, pending feedback, last activity
3. Team view: Teams, members, progress, shared XP
4. Upcoming deadlines: Missions due, pending reviews
5. Analytics: Completion rates, time-to-submit, quality metrics

Implementation:
- Aggregate queries against OpenSearch indices
- Endpoints: `GET /api/instructor/dashboard`, `GET /api/instructor/students`, `GET /api/instructor/teams`
- UI: Dashboard with tabs/cards showing different views
- Filters: by mission, by team, by date range

**Time estimate:** 2 weeks
- Schema for instructor data: 1 day
- OpenSearch aggregations: 3 days
- API endpoints: 3 days
- UI dashboard: 4 days
- Testing: 2 days

---

#### 4.2 Feedback Interface
**Scope:** Teacher review, comment, grade submissions

Currently: Brightspace-sim only

Implementation:
- Enhance existing `/api/webhooks/brightspace/review` endpoint
- Allow rich feedback (text, rubric scores, audio notes)
- New table: `feedback` (user_id, mission_id, from_user, text, rubric_scores, submitted_at)
- Event: `InsightPublished` (worker creates notifications + portfolio entries)
- UI: Feedback form with rubric, student name, submission preview

**Time estimate:** 2 weeks
- Schema: 1 day
- Rubric system: 3 days
- API enhancement: 2 days
- UI (feedback form): 4 days

---

#### 4.3 Student Monitoring
**Scope:** See who needs help, track engagement

Implementation:
- Endpoint: `GET /api/instructor/students/{user_id}` - full student view
  - XP trend over time
  - Submission history
  - Feedback history
  - Engagement (logins, days active)
  - Flags: low engagement, stuck on mission, quality concerns
- UI: Student detail page with tabs (timeline, submissions, feedback, engagement)

**Time estimate:** 1 week
- API: 2 days
- UI: 3 days

---

#### 4.4 Announcements
**Scope:** Teachers broadcast to class

Implementation:
- New table: `announcements` (org_id, from_user_id, title, text, created_at)
- Event: `AnnouncementCreated` → notification to all learners
- Endpoint: `POST /api/announcements`, `GET /api/announcements`
- UI: Announcement banner on dashboard

**Time estimate:** 1 week (low priority, can defer)

---

### Phase 4 Acceptance Criteria

- [ ] Instructor can view class overview and student list
- [ ] Instructor can review individual student progress
- [ ] Instructor can provide rich feedback with rubric
- [ ] Feedback triggers notifications and timeline updates
- [ ] Engagement metrics visible (logins, activity, streaks)
- [ ] Announcements broadcast to class

---

## Phase 5: Story Integration (2-3 weeks)

**Goal:** Narrative progression unlocks with real learning progress

### Features

#### 5.1 Story Pages / Comic
**Scope:** Narrative content shown as learner progresses

From CONCEPTS.md:
- Transmedia narrative (graphic novel + web app + Minecraft)
- Story unfolds based on mission completion
- Characters: Alex (protagonist), Ada (hacker ally), B1llbot (mentor), Alchemy (mysterious entity)
- World: Keel (mountain town), three tiers (Keel, Halyard, Oasis)

Implementation:
- New table: `story_pages` (campaign_id, sequence, mission_unlock, level_unlock, title, content_type, content_url)
- Content types: "graphic_novel_page" (image), "text_chapter", "video", "audio_log"
- Unlock triggers: mission completion, level reached
- Endpoints: `GET /api/story/pages`, `POST /api/story/pages/{page_id}/view` (mark as read)
- Events: `StoryPageUnlocked` → notification
- UI: Story reader in sidebar/modal, can progress sequentially
- Feature: "Story so far" summary for new players

**Time estimate:** 2 weeks
- Schema: 1 day
- Unlock logic: 2 days
- API: 2 days
- UI (story reader): 4 days
- Content seeding: 3 days

---

#### 5.2 NPC Dialogue
**Scope:** Characters interact with learners via B1llbot

Implementation:
- Enhance B1llbot custom model in OpenWebUI with character personas
- Prompt engineering: differentiate B1llbot vs Ada vs Alchemy vs Brokers
- Context injection: include learner's progress, mission, story page
- Endpoints: Already have `POST /api/billbot/chat`, enhance to support character parameter
- UI: Character avatar/name in chat, different colors per character

**Time estimate:** 1 week
- Prompt engineering: 3 days (writing + tuning)
- Context injection: 2 days
- UI enhancement: 2 days

---

#### 5.3 Minecraft Lore Unlocks
**Scope:** Minecraft rewards/areas tied to story progress

Implementation:
- Reward catalog: add "area_unlock" and "lore_item" reward types
- Example: Complete mission 6 → unlock Halyard tier in Minecraft
- Example: Level 10 → receive lore book with Keel history
- New Minecraft command: `/give <player> written_book` with custom lore text
- Endpoint for Minecraft bridge: read story page content, convert to book format

**Time estimate:** 1 week
- Schema: 1 day
- Minecraft book generation: 2 days
- Bridge integration: 2 days

---

### Phase 5 Acceptance Criteria

- [ ] Story pages unlock with mission/level progression
- [ ] Story reader available in UI
- [ ] Characters available via B1llbot with distinct personas
- [ ] Minecraft rewards include lore/area unlocks
- [ ] Story progression visible in learner's timeline

---

## Phase 6: Real LMS Integration (4-6 weeks)

**Goal:** Connect to real Brightspace/Moodle instead of simulator

### Features

#### 6.1 Brightspace LTI 1.3 Login
**Scope:** Students login via school's Brightspace

From `docs/process/thread3.md` (already researched)

Implementation:
- Replace `LocalIdentityProvider` with `BrightspaceLTIProvider`
- Implement LTI 1.3 Platform integration:
  - Accept LTI launch requests
  - Validate JWT
  - Create/update user in Postgres
  - Issue session token
- Endpoints: `POST /api/lti/launch` (LMS calls this)
- Configuration: Store LTI platform credentials in .env
- Testing: Use LTI simulator for testing before real Brightspace

**Time estimate:** 3 weeks
- LTI 1.3 library setup: 2 days
- Launch validation: 3 days
- User provisioning: 2 days
- Session management: 2 days
- Testing harness: 3 days

---

#### 6.2 Brightspace Assignment Submission
**Scope:** Real Dropbox submission to Brightspace

Implementation:
- Replace `SimulatedBrightspaceLMS.submit_assignment` with real API call
- Brightspace API:
  - POST `/d2l/api/le/{version}/dropbox/{dropboxId}/submissions` - submit file
  - Authenticate with OAuth2 bearer token
- Store OAuth tokens securely in .env or secure storage
- Retry logic for failed submissions (exponential backoff)

**Time estimate:** 2 weeks
- API research & auth setup: 3 days
- Submission endpoint: 3 days
- Error handling & retries: 2 days
- Testing: 3 days

---

#### 6.3 Brightspace Badge/Award Sync
**Scope:** Push learner badges back to Brightspace

Implementation:
- Use Brightspace Award Service API
- On `BadgeAwarded` event, call `POST /d2l/api/le/{version}/issuer/issuers/{issuerId}/assertions`
- Map EVOKE badges to Brightspace badge definitions (pre-configured)
- Retry logic + idempotency (don't re-issue same badge twice)

**Time estimate:** 1.5 weeks
- Badge mapping setup: 2 days
- API integration: 3 days
- Idempotency: 2 days

---

#### 6.4 Brightspace Grade Sync
**Scope:** Mission completion grades flow to gradebook

Implementation:
- On `MissionCompleted` event, write grade to Brightspace gradebook
- Grade value: mission completion status (Completed/Incomplete/Needs Revision)
- Optional: numeric score based on feedback/tier
- Brightspace API: `PUT /d2l/api/le/{version}/grades/{gradingObjectId}/values/{userId}`

**Time estimate:** 1 week
- API research: 2 days
- Integration: 2 days
- Testing: 2 days

---

#### 6.5 Moodle Integration (Future)
**Scope:** Support Moodle LMS as alternative

From ARCHITECTURE.md: "Needs its own research pass"

**Time estimate:** 4 weeks (separate pass)

---

### Phase 6 Acceptance Criteria

- [ ] Students can launch from Brightspace via LTI
- [ ] User created/updated from LTI claims
- [ ] Submissions go to Brightspace Dropbox
- [ ] Badges awarded through Brightspace badge system
- [ ] Grades sync to gradebook
- [ ] Tested with real Brightspace tenant (or robust simulator)

---

## Phase 7: Streaks & Engagement (2-3 weeks)

**Goal:** Encourage daily engagement without punishment

### Features

#### 7.1 Daily Login Streak
**Scope:** Track consecutive days of engagement

Implementation:
- New table: `streaks` (user_id, streak_type, current_count, last_date, best_count)
- Streak types: "daily_login", "mission_work", "reflection", "community"
- On each daily first-activity: check if last_date was yesterday
  - Yes: increment current_count, set last_date to today
  - No: reset current_count to 1
- XP reward: +10 for maintaining streak
- UI: Streak counter on dashboard, never shows negative/failure states

**Time estimate:** 1.5 weeks
- Schema: 1 day
- Streak calculation logic: 2 days
- XP integration: 1 day
- UI: 2 days

---

#### 7.2 Weekly Challenges (Optional)
**Scope:** Extra missions unlocked each week

Implementation:
- New table: `weekly_challenges` (week_number, challenge_id, title, description, reward_xp)
- Unlock on mission Sunday (or configurable)
- Optional; no grade depends on it
- Event: `WeeklyChallengeUnlocked`
- UI: Special badge/section on dashboard

**Time estimate:** 1 week (low priority, can defer)

---

### Phase 7 Acceptance Criteria

- [ ] Daily login streaks tracked and displayed
- [ ] Streak pauses on missed day (no punishment messaging)
- [ ] Streak bonuses awarded
- [ ] XP never removed even if streak broken

---

## Phase 8: Search (2-3 weeks)

**Goal:** Find missions, lore, feedback, community projects

### Features

#### 8.1 Full-Text Search
**Scope:** OpenSearch integration for discovery

Implementation:
- Enhance OpenSearch indices to include: missions, badges, story pages, feedback, reflections, team names
- Endpoints: `GET /api/search?q=keyword&type=missions|lore|feedback|teams`
- Filtering: by mission status, date, author, team
- Features:
  - Keyword search (e.g., "water", "Keel", "prototype")
  - Semantic search (e.g., "how to budget money" → relevant missions)
  - Type-specific search (missions only, lore only, etc.)
- UI: Search box in header, results page with filters

**Time estimate:** 2 weeks
- OpenSearch mapping refinement: 2 days
- Semantic search setup: 3 days
- API endpoint: 2 days
- UI (search + results): 4 days
- Testing: 2 days

---

#### 8.2 Smart Recommendations
**Scope:** Suggest next missions, quests, resources

Implementation:
- Recommendation algorithm:
  - Next mission: first incomplete mission in current arc
  - Suggested quests: based on current mission and skill gaps
  - Resources: if learner is stuck, suggest relevant story pages/tips
- Endpoint: `GET /api/recommendations/{user_id}`
- Feature: "Recommended for you" on dashboard

**Time estimate:** 1.5 weeks
- Algorithm design: 2 days
- Implementation: 3 days
- Testing: 2 days

---

### Phase 8 Acceptance Criteria

- [ ] Keyword search works across missions, lore, feedback
- [ ] Semantic search returns contextually relevant results
- [ ] Search UI filters by type and date
- [ ] Recommendations appear on dashboard
- [ ] Performance acceptable (<1 second queries)

---

## Phase 9: Polished UI (4-6 weeks)

**Goal:** Replace wireframe with production-quality interface

### Features

#### 9.1 Switch to `ui/` Mockup
**Scope:** Replace static HTML with design-system-based UI

The `ui/` directory already contains "Final Prosperity Showcase.html" — a polished interactive mockup

Implementation:
- Analyze mockup for component structure
- Build reusable React/Vue components (choose framework)
- API integration points: replace hardcoded data with real endpoints
- Design system: colors, typography, spacing, animation
- Responsive design: mobile-first, tablet, desktop

**Time estimate:** 6 weeks
- Component library: 2 weeks
- Page implementations: 2 weeks
- API integration: 1 week
- Testing & polish: 1 week

---

#### 9.2 Mobile Companion App (Optional)
**Scope:** Native iOS/Android for on-the-go access

Implementation:
- Reuse API endpoints from web
- Core features: check notifications, view current mission, submit evidence, chat B1llbot
- Offline-first: cache missions and story, sync when online
- Tech: React Native or Flutter

**Time estimate:** 8-12 weeks (significant effort)

---

### Phase 9 Acceptance Criteria

- [ ] UI matches design mockup
- [ ] All APIs wired and working
- [ ] Responsive on mobile/tablet/desktop
- [ ] Animations smooth and purposeful
- [ ] Accessibility (WCAG 2.1 AA)
- [ ] Loading states visible
- [ ] Error states handled gracefully

---

## Phase 10: Scaling & Ops (3-4 weeks)

**Goal:** Production deployment and monitoring

### Features

#### 10.1 Multi-Organization Deployment
**Scope:** Support multiple schools on separate servers

Implementation:
- Finalize `organizations` model (already in schema)
- One org per Postgres instance (current architecture)
- Deployment: School A runs their own stack, School B runs their own
- Shared: Nothing (each school is isolated)
- Future: Optional cloud-managed offering

**Time estimate:** 1 week
- Deployment docs: 2 days
- Testing multi-instance: 2 days
- Ops runbooks: 2 days

---

#### 10.2 Monitoring & Observability
**Scope:** Production health tracking

Implementation:
- Structured logging (JSON to stdout, aggregated by Docker)
- Metrics: Prometheus exposition format
- Dashboards: Grafana (optional)
- Alerting: Errors, performance (response times), failed jobs
- Health checks: All services report status
- Log retention: 30 days default

**Time estimate:** 2 weeks
- Structured logging setup: 3 days
- Metrics instrumentation: 3 days
- Dashboard templates: 3 days
- Alerting rules: 2 days

---

#### 10.3 Database Backups & Recovery
**Scope:** Data durability

Implementation:
- Automated daily Postgres snapshots (managed or cron)
- Test restore monthly
- Disaster recovery runbook
- PITR (point-in-time recovery) capability

**Time estimate:** 1 week
- Backup scripts: 2 days
- Restore testing: 2 days
- Runbooks: 2 days

---

#### 10.4 Performance Optimization
**Scope:** Sub-second API responses, fast UI

Implementation:
- Database indexing review
- API response caching (Redis optional)
- Frontend bundling + minification
- Image optimization
- CDN for static assets (optional)
- Load testing with 1000+ concurrent users

**Time estimate:** 2 weeks
- Profiling: 3 days
- DB optimization: 3 days
- API caching: 2 days
- Frontend optimization: 3 days

---

### Phase 10 Acceptance Criteria

- [ ] Multiple organizations can run independently
- [ ] Error rate < 0.1%
- [ ] P99 latency < 500ms
- [ ] Daily automated backups working
- [ ] Monitoring dashboards populated
- [ ] Runbooks documented
- [ ] Disaster recovery tested

---

## Phase 11: Content & Curriculum (Ongoing)

**Goal:** Expand beyond Prosperity; enable other campaigns

### Features

#### 11.1 Curriculum Authoring Tools
**Scope:** Non-technical staff can create campaigns

Implementation:
- Web UI for creating/editing missions
- Form-based: title, description, arc, superpower, PFL domain, assets
- Preview: see how mission appears to learners
- Publishing: convert to rows in missions table
- Versioning: track changes

**Time estimate:** 3 weeks
- Schema for curriculum metadata: 1 day
- CRUD endpoints: 3 days
- UI (form + preview): 5 days
- Testing: 2 days

---

#### 11.2 Resource Library
**Scope:** Reusable content (articles, videos, templates)

Implementation:
- New table: `resources` (title, type, url, campaign_id)
- Endpoint: `GET /api/resources?type=article|video|template`
- Link in missions: "See resources"
- Community contribution: teachers can suggest resources

**Time estimate:** 2 weeks

---

#### 11.3 LMS-Agnostic Content Packs
**Scope:** Pre-built campaigns for different domains

Examples:
- Healthcare: 6-week public health program
- Climate: Environmental sustainability curriculum
- Civic: Community organizing and advocacy
- Tech: Intro to software engineering

Implementation:
- Each campaign: separate data dump (missions, badges, story pages)
- Deployment: `docker compose up` + `python seed_campaign.py --campaign=healthcare`

**Time estimate:** 4-6 weeks per campaign (content-heavy)

---

### Phase 11 Acceptance Criteria

- [ ] Non-technical staff can create missions via UI
- [ ] Multiple campaigns can coexist in database
- [ ] Campaign switching works seamlessly
- [ ] Resource library integrated
- [ ] First alternative campaign (healthcare/climate/civic/tech) shipped

---

## Phase 12: Community & Gamification (3-4 weeks, Optional)

**Goal:** Encourage peer learning and healthy competition

### Features

#### 12.1 Leaderboards (Optional per org)
**Scope:** Opt-in rankings

Implementation:
- XP leaderboard: top 10 by total XP
- Weekly: top 10 this week
- Team leaderboard: teams by shared XP
- Leaderboard_config table: enable/disable per org
- Privacy: can opt out individually

**Time estimate:** 1.5 weeks

---

#### 12.2 Community Projects
**Scope:** School-wide initiatives

Implementation:
- New table: `community_projects` (title, description, goal_xp, current_xp, participants)
- Contribute: students add XP to project from missions
- Milestones: unlock when project reaches goal
- Rewards: shared badges, recognition

**Time estimate:** 2 weeks

---

#### 12.3 Mentor Network
**Scope:** Alumni / older cohorts mentor younger students

Implementation:
- Mentor matching algorithm
- Messaging system (MVP: direct email)
- Recognition: badges for mentoring

**Time estimate:** 2 weeks (low priority)

---

---

## Dependency Graph

```
MVP (Complete)
├─ Phase 1 (XP/Levels/Badges) → Phase 2 (Timeline/Portfolio)
├─ Phase 3 (Teams) → (depends on Phase 1 for XP sharing)
├─ Phase 4 (Instructor) → (depends on Phase 2 for timeline)
├─ Phase 5 (Story) → (depends on Phase 1 for level unlocks)
├─ Phase 6 (Real LMS) → (parallel)
├─ Phase 7 (Streaks) → (depends on Phase 1 for XP)
├─ Phase 8 (Search) → (depends on Phase 2 for content)
├─ Phase 9 (Polished UI) → (depends on all above)
├─ Phase 10 (Scaling) → (depends on Phase 9)
├─ Phase 11 (Content) → (parallel, depends on Phase 10)
└─ Phase 12 (Community) → (depends on Phase 1 for XP)
```

**Critical path:**
1. Phase 1 (5 weeks)
2. Phase 2 (5 weeks)
3. Phase 4 (4 weeks) in parallel with Phase 3
4. Phase 6 (5 weeks) in parallel
5. Phase 9 (6 weeks)
6. Phase 10 (4 weeks)

**Total critical path: ~24 weeks (~6 months)**

---

## Prioritization Matrix

**Must Have (MVP + Phase 1-4, 6):**
- XP/Levels/Badges
- Timeline/Portfolio
- Instructor tools
- Real LMS integration
- Achieves core learning platform functionality

**Should Have (Phase 5, 7, 8):**
- Story integration
- Streaks
- Search
- Completes narrative experience

**Nice to Have (Phase 9, 11, 12):**
- Polished UI
- Alternative campaigns
- Community features
- Scales to production
- Multiplies impact

---

## Resource Estimate

**Current:** 1 Senior Engineer + 1 AI Assistant (you)

**Phase Timeline:**
- **Weeks 1-5:** Phase 1 (XP/Levels/Badges)
- **Weeks 6-10:** Phase 2 (Timeline) + Phase 3 (Teams) parallel
- **Weeks 11-14:** Phase 4 (Instructor) + Phase 6 (Real LMS) parallel
- **Weeks 15-17:** Phase 5 (Story) + Phase 7 (Streaks) parallel
- **Weeks 18-20:** Phase 8 (Search)
- **Weeks 21-26:** Phase 9 (Polished UI)
- **Weeks 27-30:** Phase 10 (Scaling)
- **Weeks 31-32:** Phase 11 (Content) kickoff

**For faster delivery:**
- Add 1 Frontend Engineer (Weeks 21+)
- Add 1 QA/Test Engineer (Weeks 15+)
- Add 1 Content Creator (Weeks 25+)

---

## Success Criteria by Phase

| Phase | MVP Milestone | Production Ready |
|-------|---------------|------------------|
| 1 | XP shows on dashboard | XP/Levels deterministic, tested |
| 2 | Timeline view works | Portfolio exportable as PDF |
| 3 | Teams can submit together | Team badges unlock correctly |
| 4 | Instructor sees student | Rubric feedback loops |
| 5 | Story pages unlock | B1llbot character distinct |
| 6 | Real Brightspace connection | Awards sync to gradebook |
| 7 | Streaks display | No punishment messaging |
| 8 | Search returns results | Semantic search tuned |
| 9 | UI matches mockup | Accessibility AA, mobile-responsive |
| 10 | Monitoring alerts | 99.9% uptime, <500ms P99 |
| 11 | Second campaign shipped | Non-technical authoring UI |
| 12 | Leaderboard available | Privacy controls set |

---

## Notes

- Each phase includes testing, documentation, and bug fixes
- "Nice to have" features can be deferred or run in parallel with critical path
- Real LMS integration (Phase 6) should start early (research parallel with Phase 1-2)
- Story integration (Phase 5) can start as soon as narrative approved (can be Week 1 parallel task)
- Instructor experience (Phase 4) critical for school pilots; prioritize after Phase 2
- All phases assume existing MVP is stable (use Phase 0 for any MVP fixes)

---

## Next Steps

1. **Finalize roadmap with stakeholders** - Which phases are highest priority? Are there phase 12 asks?
2. **Story content approval** - Get narrative signed off for Phase 5 (can start immediately)
3. **Brightspace sandbox access** - For Phase 6 research
4. **Design system review** - Confirm UI mockup is target for Phase 9
5. **Curriculum authoring** - Start collecting feedback on Phase 11 tools
6. **Begin Phase 1** - XP/Levels/Badges system (5 weeks)
