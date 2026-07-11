#!/usr/bin/env python3
"""
Seed script for EVOKE Prosperity database
Populates with campaigns, missions, quests, users, and test data
"""

import psycopg2
import sys
import uuid

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

        # Create 12 missions
        missions_data = [
            (1, 1, 'm1', 'Explore', 'Follow the Flow', 'Deep Collaborator', 'Goal Setting', 'Explore water patterns in Keel'),
            (1, 2, 'm2', 'Explore', 'Money Moves', 'Empathetic Changemaker', 'Budgeting', 'Track personal spending'),
            (2, 3, 'm3', 'Imagine', 'Building Blocks', 'Systems Thinker', 'Investing', 'Design an investment strategy'),
            (2, 4, 'm4', 'Imagine', 'Pitch Perfect', 'Creative Visionary', 'Goal Setting', 'Develop a pitch for a venture'),
            (3, 5, 'm5', 'Act', 'Risk and Reward', 'Systems Thinker', 'Investing', 'Evaluate risk profiles'),
            (3, 6, 'm6', 'Act', 'Market Makers', 'Empathetic Changemaker', 'Budgeting', 'Create a social enterprise'),
            (4, 7, 'm7', 'Communicate', 'Community Capital', 'Deep Collaborator', 'Philanthropy', 'Build community support'),
            (4, 8, 'm8', 'Communicate', 'Digital Economy', 'Creative Visionary', 'Investing', 'Navigate digital markets'),
            (5, 9, 'm9', 'Act', 'Sustainable Growth', 'Systems Thinker', 'Goal Setting', 'Create sustainability plan'),
            (5, 10, 'm10', 'Act', 'Global Markets', 'Empathetic Changemaker', 'Budgeting', 'Understand global trade'),
            (6, 11, 'm11', 'Communicate', 'Craft Your Pitch', 'Creative Visionary', 'Philanthropy', 'Refine final pitch'),
            (6, 12, 'm12', 'Communicate', 'Worth Backing', 'Deep Collaborator', 'Investing', 'Present venture for backing'),
        ]

        mission_ids = {}
        for week, seq, key, arc, title, superpower, pfl_domain, description in missions_data:
            mission_id = uuid.uuid4()
            cur.execute(
                """INSERT INTO missions
                   (id, campaign_id, lms_assignment_ref, week, sequence, title, arc, superpower, primary_skill, pfl_domain, mission_brief_md)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (mission_id, campaign_id, key, week, seq, title, arc, superpower, superpower, pfl_domain, description)
            )
            mission_ids[key] = mission_id

        # Create Minecraft quests (one per mission + side quests)
        quest_data = [
            ('mission-1', None, 'Follow the Flow', 'Explore the abandoned pumping station', 'mission_quest'),
            ('mission-2', None, 'Track Your Resources', 'Collect resources and organize your inventory', 'mission_quest'),
            ('mission-3', None, 'Build the Base', 'Construct a shelter representing your investment', 'mission_quest'),
            ('mission-4', None, 'The Great Pitch', 'Create a banner for your venture', 'mission_quest'),
            ('mission-5', None, 'Risk Assessment', 'Explore dangerous terrain to understand risk', 'mission_quest'),
            ('mission-6', None, 'Market Hub', 'Set up a trading station', 'mission_quest'),
            ('mission-7', None, 'Community Hall', 'Build a gathering space', 'mission_quest'),
            ('mission-8', None, 'Digital Marketplace', 'Create a shop with villager trading', 'mission_quest'),
            ('mission-9', None, 'Green Initiative', 'Build a sustainable farm', 'mission_quest'),
            ('mission-10', None, 'Trade Routes', 'Establish transportation network', 'mission_quest'),
            ('mission-11', None, 'Presentation Stage', 'Build a stage for your pitch', 'mission_quest'),
            ('mission-12', None, 'The Grand Opening', 'Open your venture to the Basin', 'mission_quest'),
            # Side quests
            (None, None, 'Find Hidden Treasure', 'Locate 5 hidden chests in the Basin', 'side_quest'),
            (None, None, 'Master Farmer', 'Harvest crops from all biomes', 'side_quest'),
            (None, None, 'Mining Expert', 'Collect rare ores and materials', 'side_quest'),
            (None, None, "Explorer's Log", 'Map out the entire Basin', 'side_quest'),
        ]

        for mission_key, mission_ref, title, description, kind in quest_data:
            quest_id = uuid.uuid4()
            mission_id = mission_ids.get(mission_key)

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
        print(f"  - Missions: 12 created")
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
