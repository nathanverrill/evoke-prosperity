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

        # Two default users, not four -- Player One is the primary
        # learner-facing default (what dev-login returns with no params);
        # Admin is the operator identity, deliberately using the same email
        # OpenWebUI's admin account uses (see openwebui-bootstrap.py) so
        # it's recognizably the same person across both systems. There's no
        # shared password auth between them (evoke's dev-login has no
        # password concept at all) -- this is identity alignment, not SSO.
        player_one_id = uuid.uuid4()
        cur.execute(
            "INSERT INTO users (id, org_id, display_name, email, role) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (player_one_id, org_id, 'Player One', 'player1@evoke.local', 'learner')
        )

        # Add local auth identity
        cur.execute(
            "INSERT INTO auth_identities (user_id, provider, provider_subject) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (player_one_id, 'local', 'player1@evoke.local')
        )

        admin_id = uuid.uuid4()
        cur.execute(
            "INSERT INTO users (id, org_id, display_name, email, role) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (admin_id, org_id, 'Admin', 'admin@evoke.local', 'admin')
        )

        cur.execute(
            "INSERT INTO auth_identities (user_id, provider, provider_subject) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (admin_id, 'local', 'admin@evoke.local')
        )

        # Create team
        team_id = uuid.uuid4()
        cur.execute(
            "INSERT INTO teams (id, org_id, name) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (team_id, org_id, 'Demo Team')
        )

        cur.execute(
            "INSERT INTO team_members (team_id, user_id, role_label) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (team_id, player_one_id, 'Leader')
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
            # Not a mission-tier award -- delivered by the daily web check-in
            # (POST /api/checkin), reusing this exact same tier-keyed reward
            # pipeline. Deliberately a single small/cosmetic entry (a compass
            # -- "find your way back to the mission"), not a duplicate-tier
            # ambiguity like the pairs above where the bridge's "LIMIT 1"
            # query arbitrarily picks one of two rows.
            'checkin': [
                ('item', 'minecraft:compass', 1, None, False),
            ],
            # Small, harmless flavor items handed out at random to anyone
            # online in Minecraft (evoke-minecraft-bridge's heartbeat loop) --
            # not a mission/badge reward, just a "the pipeline is alive"
            # signal, so deliberately not tier-ranked with the real rewards
            # above and never anything an economy/inventory decision hinges
            # on.
            'ambient': [
                ('item', 'minecraft:paper', 1, None, False),
                ('item', 'minecraft:torch', 4, None, False),
                ('item', 'minecraft:bread', 2, None, False),
                ('item', 'minecraft:poppy', 1, None, False),
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

        # Deliberately NOT pre-linking Player One to a Minecraft username
        # here -- evoke-minecraft-bridge's heartbeat loop auto-links the
        # first real player it ever sees online to Player One (see
        # PLAYER_ONE_EMAIL in bridge.py). Pre-seeding a fake "DemoLearner"
        # link here would make that detection logic untestable (it would
        # see Player One as already linked and never run).

        conn.commit()
        print("✓ Database seeded successfully")
        print(f"  - Campaign: evoke-prosperity")
        print(f"  - Organization: Demo School")
        print(f"  - Player One (learner): {player_one_id}")
        print(f"  - Admin: {admin_id}")
        print(f"  - Missions: synced from the LMS on EVOKE app startup, not seeded here")
        print(f"  - Quests: 16 created")
        print(f"  - Minecraft: unlinked -- connect a real client and evoke-minecraft-bridge will auto-link the first player to Player One")

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
