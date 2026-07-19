-- EVOKE Prosperity Database Schema

-- Campaigns
CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Organizations
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    active_campaign_id UUID NOT NULL REFERENCES campaigns(id),
    lms_type VARCHAR(50) NOT NULL CHECK (lms_type IN ('brightspace', 'moodle')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    display_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('learner', 'instructor', 'admin')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- evoke/identity.py's get_or_create_evoke_player targets this in its
    -- ON CONFLICT (email, org_id) clause -- without it, that INSERT is
    -- invalid SQL and 500s on every call (found live, 2026-07-16: this
    -- constraint had never actually existed, so the LTI auto-provisioning
    -- path had never successfully created a new user).
    UNIQUE(email, org_id)
);

-- Auth Identities
CREATE TABLE auth_identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('local', 'brightspace', 'moodle')),
    provider_subject VARCHAR(255),
    password_hash VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, provider)
);

-- Teams
CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- evoke/identity.py's sync_team_membership targets this in its
    -- ON CONFLICT (org_id, name) clause, to get-or-create a team matching a
    -- Brightspace Group's name -- added live via ALTER TABLE on the running
    -- dev Postgres 2026-07-18 (see the users(email, org_id) constraint above
    -- for why that matters: an ON CONFLICT clause with no matching
    -- constraint is invalid SQL, not a silent no-op).
    UNIQUE(org_id, name)
);

-- Team Members
CREATE TABLE team_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id),
    user_id UUID NOT NULL REFERENCES users(id),
    role_label VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, user_id)
);

-- Badges
CREATE TABLE badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id),
    key VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campaign_id, key)
);

-- Missions
CREATE TABLE missions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id),
    lms_assignment_ref VARCHAR(255),
    week INTEGER,
    sequence INTEGER,
    title VARCHAR(255) NOT NULL,
    arc VARCHAR(50) CHECK (arc IN ('Explore', 'Imagine', 'Act', 'Communicate')),
    superpower VARCHAR(100),
    primary_skill VARCHAR(100),
    secondary_skill VARCHAR(100),
    pfl_domain VARCHAR(100),
    pbl_description TEXT,
    mission_brief_md TEXT,
    evidence_requirements_md TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- NULL = not yet released to learners. Gating is manual admin release,
    -- not automatic order-of-completion -- see GAPS.md's now-resolved
    -- "mission ordering" item. Deliberately excluded from the LMS sync's
    -- ON CONFLICT UPDATE SET (main.py) so re-syncing the catalog never
    -- resets a mission an admin already released.
    released_at TIMESTAMP,
    -- The LMS (brightspace-sim, or real Brightspace later) is the system of
    -- record for the mission catalog; this table is a synced cache keyed by
    -- (campaign_id, lms_assignment_ref) so the startup sync can upsert
    -- instead of duplicating a mission every restart.
    UNIQUE(campaign_id, lms_assignment_ref)
);

-- Awards
CREATE TABLE awards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    mission_id UUID NOT NULL REFERENCES missions(id),
    tier VARCHAR(50) NOT NULL CHECK (tier IN ('common', 'uncommon', 'rare', 'epic', 'legendary')),
    source VARCHAR(50) NOT NULL CHECK (source IN ('submission', 'ai_review', 'teacher_review')),
    awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notified_at TIMESTAMP,
    collected_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, mission_id, tier, source)
);

-- Notifications
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    award_id UUID REFERENCES awards(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP
);

-- Minecraft Links
CREATE TABLE minecraft_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    server_id VARCHAR(255),
    minecraft_uuid VARCHAR(36),
    minecraft_username VARCHAR(255),
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, server_id)
);

-- Minecraft Reward Catalog
CREATE TABLE mc_reward_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id),
    badge_id UUID REFERENCES badges(id),
    tier VARCHAR(50),
    reward_type VARCHAR(50) NOT NULL CHECK (reward_type IN ('item', 'effect', 'command')),
    reward VARCHAR(255) NOT NULL,
    reward_amount INTEGER,
    duration INTEGER,
    persistent BOOLEAN DEFAULT false,
    reward_tier VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Minecraft Reward Grants
CREATE TABLE mc_reward_grants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    server_id VARCHAR(255),
    catalog_id UUID REFERENCES mc_reward_catalog(id),
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT true,
    executed BOOLEAN DEFAULT false
);

-- Minecraft Quests
CREATE TABLE mc_quests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id),
    mission_id UUID REFERENCES missions(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    kind VARCHAR(50) NOT NULL CHECK (kind IN ('mission_quest', 'side_quest')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Minecraft Quest Completions
CREATE TABLE mc_quest_completions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    quest_id UUID NOT NULL REFERENCES mc_quests(id),
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Minecraft Quest Submissions
CREATE TABLE mc_quest_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quest_id UUID NOT NULL REFERENCES mc_quests(id),
    user_id UUID NOT NULL REFERENCES users(id),
    observation_text TEXT,
    screenshot_object_key VARCHAR(255),
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EVOKE Identity Mapping (cross-system ID linking)
CREATE TABLE evoke_identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    brightspace_user_id INTEGER UNIQUE,
    minecraft_uuid VARCHAR(36) UNIQUE,
    minecraft_username VARCHAR(16),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, brightspace_user_id)
);

-- Submissions (for tracking LMS assignment submissions)
CREATE TABLE submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Who physically submitted (attribution/feed messages only, as of the
    -- team-evidence model -- see team_id below for the real completion key).
    user_id UUID NOT NULL REFERENCES users(id),
    mission_id UUID NOT NULL REFERENCES missions(id),
    -- The team's shared evidence artifact -- any member can submit it, and
    -- it's owned by the team, not the submitter. NULL only for historical
    -- rows that predate this column.
    team_id UUID REFERENCES teams(id),
    brightspace_submission_id VARCHAR(255),
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_path VARCHAR(500),
    status VARCHAR(50) DEFAULT 'submitted',
    reflection TEXT,
    grade INTEGER,
    feedback TEXT,
    graded_at TIMESTAMP,
    UNIQUE(user_id, mission_id, submitted_at)
);

-- Each individual team member's own reflection on a mission -- required,
-- separately from the team's shared evidence above, to receive their own
-- award/XP (an AND-gate: see main.py's _complete_mission_for_user). Not the
-- same thing as daily_reflections (the Field Report/Wisdom Journal), which
-- is unrelated and once-a-day.
CREATE TABLE mission_reflections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    mission_id UUID NOT NULL REFERENCES missions(id),
    team_id UUID NOT NULL REFERENCES teams(id),
    reflection TEXT NOT NULL,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, mission_id)
);

-- Badge to Brightspace Award mapping
CREATE TABLE badge_brightspace_mapping (
    badge_id UUID NOT NULL REFERENCES badges(id),
    brightspace_award_id INTEGER NOT NULL,
    campaign_id UUID NOT NULL REFERENCES campaigns(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(badge_id, campaign_id)
);

-- Mission to Brightspace Assignment mapping
CREATE TABLE mission_brightspace_mapping (
    mission_id UUID NOT NULL REFERENCES missions(id),
    brightspace_assignment_id VARCHAR(50) NOT NULL,
    campaign_id UUID NOT NULL REFERENCES campaigns(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(mission_id, campaign_id)
);

-- Web Check-Ins (a reason to open the Operations Hub between missions --
-- weekly-paced missions mean personal activity is sparse most days; this
-- and the activity feed are what make visiting the site worthwhile anyway.
-- One row per user per calendar day -- non-punitive by construction, since
-- there's no streak counter here to break, just "did you check in today".)
CREATE TABLE checkins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    checkin_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, checkin_date)
);

-- GAME_DESIGN.md §4.1: Generosity of Spirit and Curiosity have zero
-- coverage in the 12 missions' fixed Primary/Secondary tags, so they're
-- unlocked by behavior instead. These two tables give a reliable count to
-- threshold against (an OpenSearch query over InsightPublished-derived
-- projections would work for the peer-insight count, but not for chat
-- volume, which nothing else logs at all).
CREATE TABLE peer_insights_given (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_user_id UUID NOT NULL REFERENCES users(id),
    target_user_id UUID NOT NULL REFERENCES users(id),
    mission_id UUID NOT NULL REFERENCES missions(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE billbot_chat_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Browser minigame ("Training Sim") score log + the Alchemy Signal
-- scavenger-hunt fragments (game_key 'signal:<fragment>' rows, score=1).
-- Append-only; personal bests and daily-XP dedupe are computed by query.
-- main.py also CREATE TABLE IF NOT EXISTS this for pre-existing volumes.
CREATE TABLE minigame_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    game_key VARCHAR(64) NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_minigame_scores_user_game ON minigame_scores(user_id, game_key);
CREATE INDEX idx_minigame_scores_game_score ON minigame_scores(game_key, score DESC);

-- Scoreboard-driven quest triggers: "the world reports itself"
-- (GAME_DESIGN.md §6.2's implementation note: wire QuestCompleted to the
-- real in-world mechanics' scoreboards instead of relying on self-report).
-- The bridge polls each linked player's score for `objective`; score >=
-- threshold auto-completes the mapped quest through the normal pipeline.
-- Rows are seeded idempotently by main.py startup (title-keyed), so this
-- also works on pre-existing volumes.
CREATE TABLE mc_quest_triggers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quest_id UUID NOT NULL REFERENCES mc_quests(id),
    objective VARCHAR(64) NOT NULL,
    threshold INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(quest_id, objective)
);

-- Small key-value store for world-anchored facts the bridge must remember
-- across restarts -- currently just 'beacon_pos', the spot where the Keel
-- Restoration Beacon was anchored (see evoke-minecraft-bridge/bridge.py's
-- _get_beacon_anchor; the bridge also CREATE TABLE IF NOT EXISTS this, so
-- existing volumes that predate this file's version work too).
CREATE TABLE world_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Indexes for common queries
CREATE INDEX idx_users_org_id ON users(org_id);
CREATE INDEX idx_teams_org_id ON teams(org_id);
CREATE INDEX idx_missions_campaign_id ON missions(campaign_id);
CREATE INDEX idx_awards_user_id ON awards(user_id);
CREATE INDEX idx_awards_mission_id ON awards(mission_id);
CREATE INDEX idx_awards_user_mission ON awards(user_id, mission_id);
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_minecraft_links_user_id ON minecraft_links(user_id);
CREATE INDEX idx_mc_quest_completions_user_id ON mc_quest_completions(user_id);
CREATE INDEX idx_evoke_identities_user_id ON evoke_identities(user_id);
CREATE INDEX idx_evoke_identities_brightspace ON evoke_identities(brightspace_user_id);
CREATE INDEX idx_evoke_identities_minecraft ON evoke_identities(minecraft_uuid);
CREATE INDEX idx_checkins_user_date ON checkins(user_id, checkin_date);
CREATE INDEX idx_peer_insights_from_user ON peer_insights_given(from_user_id);
CREATE INDEX idx_billbot_chat_log_user ON billbot_chat_log(user_id);
CREATE INDEX idx_submissions_user_mission ON submissions(user_id, mission_id);
CREATE INDEX idx_submissions_brightspace_id ON submissions(brightspace_submission_id);

-- Create initial campaign
INSERT INTO campaigns (key, name, description) VALUES
('evoke-prosperity', 'EVOKE Prosperity', 'A 6-week financial literacy and entrepreneurship curriculum set in the mountain town of Keel')
ON CONFLICT DO NOTHING;
