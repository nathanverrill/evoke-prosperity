#!/usr/bin/env python3
"""
Seed script for EVOKE Prosperity database
Populates with campaigns, missions, quests, users, and test data
"""

import psycopg2
import psycopg2.extras
import sys
import uuid

# Without this, psycopg2 can't adapt Python uuid.UUID objects to Postgres UUID
# columns at all ("can't adapt type 'UUID'") -- every uuid.uuid4() passed as a
# query param below needs it. This was missing, so this script has never
# actually completed a run; it fails on the very first UUID-bearing INSERT.
psycopg2.extras.register_uuid()

# Database connection
def get_connection(db_url):
    return psycopg2.connect(db_url)

def seed_database(db_url):
    conn = get_connection(db_url)
    cur = conn.cursor()

    try:
        # Get or create campaign
        cur.execute("SELECT id FROM campaigns WHERE key = 'evoke-prosperity'")
        campaign_result = cur.fetchone()
        if campaign_result:
            campaign_id = campaign_result[0]
        else:
            campaign_id = uuid.uuid4()
            cur.execute(
                "INSERT INTO campaigns (id, key, name, description) VALUES (%s, %s, %s, %s)",
                (campaign_id, 'evoke-prosperity', 'EVOKE Prosperity', 'A 6-week financial literacy and entrepreneurship curriculum')
            )

        # Create organization
        org_id = uuid.uuid4()
        cur.execute(
            "INSERT INTO organizations (id, name, active_campaign_id, lms_type) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (org_id, 'Demo School', campaign_id, 'brightspace')
        )

        # Create test users
        learner_id = uuid.uuid4()
        cur.execute(
            "INSERT INTO users (id, org_id, display_name, email, role) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (learner_id, org_id, 'Demo Learner', 'learner@evoke.local', 'learner')
        )

        # Add local auth identity
        cur.execute(
            "INSERT INTO auth_identities (user_id, provider, provider_subject) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (learner_id, 'local', 'learner@evoke.local')
        )

        teacher_id = uuid.uuid4()
        cur.execute(
            "INSERT INTO users (id, org_id, display_name, email, role) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (teacher_id, org_id, 'Demo Teacher', 'teacher@evoke.local', 'instructor')
        )

        cur.execute(
            "INSERT INTO auth_identities (user_id, provider, provider_subject) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (teacher_id, 'local', 'teacher@evoke.local')
        )

        # Create team
        team_id = uuid.uuid4()
        cur.execute(
            "INSERT INTO teams (id, org_id, name) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (team_id, org_id, 'Demo Team')
        )

        cur.execute(
            "INSERT INTO team_members (team_id, user_id, role_label) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (team_id, learner_id, 'Leader')
        )

        # Create badges (Superpowers)
        superpowers = [
            ('empathetic-changemaker', 'Empathetic Changemaker'),
            ('systems-thinker', 'Systems Thinker'),
            ('creative-visionary', 'Creative Visionary'),
            ('deep-collaborator', 'Deep Collaborator'),
        ]

        badge_ids = {}
        for key, name in superpowers:
            badge_id = uuid.uuid4()
            cur.execute(
                "INSERT INTO badges (id, campaign_id, key, name, category) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (badge_id, campaign_id, key, name, 'superpower')
            )
            badge_ids[key] = badge_id

        # Missions are no longer seeded here -- the LMS (brightspace-sim) is
        # the system of record for the mission catalog, and EVOKE syncs its
        # missions table from it on startup (see main.py's
        # sync_missions_from_lms, keyed by lms_assignment_ref). Run this
        # script AFTER starting the EVOKE app at least once, or the quest
        # links below will warn and fall back to unlinked (mission_id=NULL).
        #
        # NOTE on the mission_id lookups below: the previous version of this
        # script built an in-memory mission_key -> mission_id map from its
        # own mission-seeding loop, but the quest_data keys ('mission-1',
        # 'mission-2', ...) never actually matched that map's keys ('m1',
        # 'm2', ...) -- every mission_quest silently got mission_id=NULL,
        # indistinguishable from a side_quest by foreign key alone. Fixed by
        # querying the real missions table by lms_assignment_ref instead of
        # relying on an in-process dict built from placeholder data.
        def get_mission_id(lms_ref):
            if not lms_ref:
                return None
            cur.execute(
                "SELECT id FROM missions WHERE campaign_id = %s AND lms_assignment_ref = %s",
                (campaign_id, lms_ref)
            )
            row = cur.fetchone()
            if not row:
                print(f"  ! No mission synced yet for {lms_ref} -- quest will link to no mission until the EVOKE app has run its startup sync")
            return row[0] if row else None

        # Create Minecraft quests (one per mission + side quests)
        quest_data = [
            ('mission-01', 'Walk the Mountain', 'Explore Keel, Halyard, and Oasis before any missions unlock', 'mission_quest'),
            ('mission-02', 'Carve Your Cup', 'Carve a personal cup from recycled pipe metal in Keel', 'mission_quest'),
            ('mission-03', 'Blueprint Table', 'Sketch your team\'s wildest ideas in the Keel workshop', 'mission_quest'),
            ('mission-04', 'Vision Beacon', 'Build a marker showing your 2035 vision', 'mission_quest'),
            ('mission-05', 'Factory Crafting I', 'Plan a resource-flow production line in Halyard', 'mission_quest'),
            ('mission-06', 'Factory Crafting II', 'Stress-test your production line against a supply shock', 'mission_quest'),
            ('mission-07', 'Salvage & Build', 'Recover abandoned Alpha Dynamics infrastructure in Halyard', 'mission_quest'),
            ('mission-08', 'Reroute', 'Iterate on your build after a complication', 'mission_quest'),
            ('mission-09', 'Open the Gates', 'Invite others to react to your build in-world', 'mission_quest'),
            ('mission-10', 'The Vault', 'Allocate resources between your build and the shared network', 'mission_quest'),
            ('mission-11', 'Pitch Hall', 'Stage your build in the newly-unlocked Oasis', 'mission_quest'),
            ('mission-12', 'Network Node', 'Connect your build to the growing network map', 'mission_quest'),
            # Side quests
            (None, 'Find Hidden Treasure', 'Locate 5 hidden chests in the Basin', 'side_quest'),
            (None, 'Master Farmer', 'Harvest crops from all biomes', 'side_quest'),
            (None, 'Mining Expert', 'Collect rare ores and materials', 'side_quest'),
            (None, "Explorer's Log", 'Map out the entire Basin', 'side_quest'),
        ]

        for lms_ref, title, description, kind in quest_data:
            quest_id = uuid.uuid4()
            mission_id = get_mission_id(lms_ref)

            cur.execute(
                """INSERT INTO mc_quests (id, campaign_id, mission_id, title, description, kind)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (quest_id, campaign_id, mission_id, title, description, kind)
            )

        # Create Minecraft reward catalog (tier-based rewards)
        tiers = ['common', 'uncommon', 'rare', 'epic', 'legendary']
        rewards = {
            'common': [
                ('item', 'minecraft:stone', 1, None, False),
                ('item', 'minecraft:dirt', 64, None, False),
            ],
            'uncommon': [
                ('item', 'minecraft:iron_pickaxe', 1, None, False),
                ('effect', 'minecraft:haste', 60, 300, True),
            ],
            'rare': [
                ('item', 'minecraft:diamond', 8, None, False),
                ('effect', 'minecraft:speed', 120, 600, True),
            ],
            'epic': [
                ('item', 'minecraft:diamond_pickaxe', 1, None, False),
                ('effect', 'minecraft:strength', 180, 900, True),
            ],
            'legendary': [
                ('item', 'minecraft:netherite_pickaxe', 1, None, False),
                ('command', 'give <player> minecraft:enchanted_golden_apple', 1, None, False),
            ],
        }

        for tier, reward_list in rewards.items():
            for reward_type, reward, amount, duration, persistent in reward_list:
                catalog_id = uuid.uuid4()
                cur.execute(
                    """INSERT INTO mc_reward_catalog
                       (id, campaign_id, tier, reward_type, reward, reward_amount, duration, persistent)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT DO NOTHING""",
                    (catalog_id, campaign_id, tier, reward_type, reward, amount, duration, persistent)
                )

        # Link test user to Minecraft
        cur.execute(
            "INSERT INTO minecraft_links (user_id, server_id, minecraft_username) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (learner_id, 'default', 'DemoLearner')
        )

        conn.commit()
        print("✓ Database seeded successfully")
        print(f"  - Campaign: evoke-prosperity")
        print(f"  - Organization: Demo School")
        print(f"  - Test Learner: {learner_id}")
        print(f"  - Test Teacher: {teacher_id}")
        print(f"  - Missions: synced from the LMS on EVOKE app startup, not seeded here")
        print(f"  - Quests: 16 created")
        print(f"  - Minecraft Username: DemoLearner")

    except Exception as e:
        conn.rollback()
        print(f"✗ Seeding failed: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    db_url = "postgresql://evoke:devsecret123@localhost:5432/evoke"
    seed_database(db_url)
