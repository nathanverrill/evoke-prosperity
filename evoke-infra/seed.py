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

        # Get or create organization -- same pattern as campaigns above, and
        # for the same reason: org_id is used throughout the rest of this
        # script, so ON CONFLICT DO NOTHING alone isn't enough now that
        # organizations.name is actually unique (previously wasn't, which is
        # why re-running this script used to silently multiply "Demo School"
        # on every run -- fixed 2026-07-21). A skipped insert would leave
        # org_id pointing at a row that was never created, breaking every
        # INSERT below that references it.
        cur.execute("SELECT id FROM organizations WHERE name = %s", ('Demo School',))
        org_result = cur.fetchone()
        if org_result:
            org_id = org_result[0]
        else:
            org_id = uuid.uuid4()
            cur.execute(
                "INSERT INTO organizations (id, name, active_campaign_id, lms_type) VALUES (%s, %s, %s, %s)",
                (org_id, 'Demo School', campaign_id, 'brightspace')
            )

        # Three default users, not four -- Player One is the primary
        # learner-facing default (what dev-login returns with no params);
        # Player Two exists so the team-evidence AND-gate
        # (_complete_mission_for_user in main.py: shared team submission +
        # EACH member's own reflection) is actually testable locally --
        # that gate structurally needs two distinct people, and a solo dev
        # can't simulate a teammate with one account. Admin is the operator
        # identity, deliberately using the same email OpenWebUI's admin
        # account uses (see openwebui-bootstrap.py) so it's recognizably the
        # same person across both systems. There's no shared password auth
        # between any of these (evoke's dev-login has no password concept at
        # all) -- this is identity alignment, not SSO.
        # Upsert with RETURNING, not INSERT ... ON CONFLICT DO NOTHING plus a
        # locally-generated id -- found live, 2026-07-21, right after fixing
        # organizations' own duplication bug above: once org_id reliably
        # resolves to the same real row every run, a re-run's user insert
        # legitimately conflicts (the account already exists), and a bare
        # ON CONFLICT DO NOTHING silently skips the row while this script
        # keeps using the *unused* uuid.uuid4() it generated -- the very next
        # auth_identities insert then references a user_id that was never
        # actually written, a foreign-key violation that aborts the whole
        # run. Previously masked entirely: every prior run created a brand
        # new org, so these inserts always succeeded for real and the bug
        # never had a chance to fire. RETURNING id makes the local variable
        # correct in both the create and the already-exists case.
        def upsert_user(display_name, email, role):
            cur.execute(
                """INSERT INTO users (id, org_id, display_name, email, role)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (email, org_id) DO UPDATE SET display_name = EXCLUDED.display_name
                   RETURNING id""",
                (uuid.uuid4(), org_id, display_name, email, role)
            )
            return cur.fetchone()[0]

        player_one_id = upsert_user('Player One', 'player1@evoke.local', 'learner')
        cur.execute(
            "INSERT INTO auth_identities (user_id, provider, provider_subject) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (player_one_id, 'local', 'player1@evoke.local')
        )

        player_two_id = upsert_user('Player Two', 'player2@evoke.local', 'learner')
        cur.execute(
            "INSERT INTO auth_identities (user_id, provider, provider_subject) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (player_two_id, 'local', 'player2@evoke.local')
        )

        admin_id = upsert_user('Admin', 'admin@evoke.local', 'admin')
        cur.execute(
            "INSERT INTO auth_identities (user_id, provider, provider_subject) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (admin_id, 'local', 'admin@evoke.local')
        )

        # Get or create team -- same RETURNING-based fix as the user upserts
        # above, and for the same reason: team_id is used immediately below
        # for team_members, so a silently-skipped insert (a real possibility
        # now that org_id is stable across runs) would leave it pointing at
        # a team that was never actually created. Same idiom identity.py's
        # sync_team_membership already uses for this exact table.
        cur.execute(
            """INSERT INTO teams (id, org_id, name) VALUES (%s, %s, %s)
               ON CONFLICT (org_id, name) DO UPDATE SET name = teams.name
               RETURNING id""",
            (uuid.uuid4(), org_id, 'Demo Team')
        )
        team_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO team_members (team_id, user_id, role_label) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (team_id, player_one_id, 'Leader')
        )
        cur.execute(
            "INSERT INTO team_members (team_id, user_id, role_label) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (team_id, player_two_id, 'Member')
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
            # Side quests: the Keel Mine expedition line (2026-07-22).
            # "Explore" and "Descend to Keel" aren't repeated here -- they're
            # the existing Basin Archive entries seeded further down.
            (None, 'Speak with B1llBot', 'Find B1llBot in Keel and say hello.', 'side_quest'),
            (None, 'Enter the Keel Mine', 'Step through the Keel Mine entrance.', 'side_quest'),
            (None, 'Mine 32 Coal', 'Mine 32 coal ore in the Keel Mine.', 'side_quest'),
            (None, 'Mine 16 Iron Ore', 'Mine 16 iron ore in the Keel Mine.', 'side_quest'),
            (None, 'Return to town', 'Carry your haul back to Keel.', 'side_quest'),
            (None, 'Sell your ores at the Marketplace', 'Trade your coal and iron for coins at the Marketplace.', 'side_quest'),
            (None, 'Earn your first coins', 'Walk away from the Marketplace with money in your pocket.', 'side_quest'),
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

        # Create Minecraft reward catalog (tier-based reward SETS -- the
        # bridge delivers every row for the tier, not LIMIT 1). Design per
        # MINECRAFT_REWARDS.md: identity > utility, buffs time-bounded,
        # money grants small vs. earned wages, nothing that skips the
        # game's own progression (no free high-tier tools -- the old
        # diamond/netherite pickaxes trivialized the entire mines economy).
        # For 'effect' rows, reward_amount = the effect amplifier (0 = level
        # I) and duration is in ticks. 'command' rows may use <player> and
        # <mission_title> placeholders (rendered by the bridge).
        tiers = ['common', 'uncommon', 'rare', 'epic', 'legendary']
        rewards = {
            'common': [
                ('command', 'give <player> minecraft:written_book[minecraft:written_book_content={title:"Field Commendation",author:"B1llbot",pages:[{raw:{text:"Commendation for completing <mission_title>. The Basin grows stronger.\\n\\n— B1llbot"}}]}] 1', 1, None, False),
                ('command', 'givemoney <player> 10', 1, None, False),
                ('effect', 'minecraft:haste', 0, 12000, False),
            ],
            'uncommon': [
                ('effect', 'minecraft:night_vision', 0, 12000, False),
                ('command', 'givemoney <player> 15', 1, None, False),
            ],
            'rare': [
                ('effect', 'minecraft:speed', 1, 18000, False),
                ('item', 'minecraft:paper', 1, None, False),
                ('command', 'givemoney <player> 20', 1, None, False),
            ],
            'epic': [
                ('effect', 'minecraft:hero_of_the_village', 0, 36000, False),
                ('command', 'give <player> minecraft:gold_ingot[minecraft:custom_name="Guild Standing",minecraft:lore=["For excellence in the field","— B1llbot"]] 1', 1, None, False),
                ('command', 'givemoney <player> 30', 1, None, False),
            ],
            'legendary': [
                ('command', 'execute at <player> run summon minecraft:allay ~ ~1 ~ {PersistenceRequired:1b,CustomName:"Alpha Courier Drone",CustomNameVisible:1b,Tags:["mission_companion"]}', 1, None, False),
                ('effect', 'minecraft:glowing', 0, 12000, False),
                ('command', 'execute at <player> run particle minecraft:firework ~ ~1 ~ 1 1 1 0.15 300', 1, None, False),
                ('command', 'execute at <player> run playsound minecraft:entity.firework_rocket.large_blast master @a ~ ~ ~ 1 1', 1, None, False),
                ('command', 'givemoney <player> 50', 1, None, False),
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
        print(f"  - Player One (learner, Demo Team Leader): {player_one_id}")
        print(f"  - Player Two (learner, Demo Team Member): {player_two_id}")
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
