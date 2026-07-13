"""Field Gear — displayable equipment unlocked by *combinations* of real
progress (Powers earned, rank, minigame mastery, Alchemy fragments, Basin
play), worn on the Agent Dossier. Purely cosmetic/identity: gear never
gates a mission, never grants XP, never touches the award pipeline —
it's the loadout half of the Dossier, a visible answer to "what kind of
agent are you," in the same hard-sci-fi register as the rest of the Basin.

Design rules:
- Every unlock condition reads *existing* facts (player-profile projection,
  Postgres logs) — no new events, no new counters to maintain. Unlocks are
  computed at read time, so they can never drift from the truth.
- Conditions are combinations on purpose (the ask): a piece of gear should
  feel like a *build*, not a checkbox — e.g. the Cistern Core needs both
  rank and Flow Control mastery.
- Hints are always shown (motivating, not mysterious) except gear tied to
  the Alchemy Signal, which stays cryptic by that feature's own rules.

Slots are flavor (grouping on the Dossier), not mechanics. Rarity reuses
the existing tier language: standard / epic / legendary.
"""

# Each item: key, name, slot, rarity, icon (text glyph), flavor line,
# hint (what to do), secret (hide hint until unlocked), and `needs` — a
# dict of requirement -> value, ALL of which must hold (combinations).
#
# Requirement vocabulary (evaluated by evaluate_gear below):
#   level            — profile level >= N
#   missions         — missions completed >= N
#   quests           — Basin quests logged >= N
#   powers           — list of specific Power names, all earned
#   powers_in        — (quality, n): >= n Powers earned within one Quality
#   qualities        — number of fully-earned Quality badges >= N
#   game_best        — (game_key, score): personal best >= score
#   games_played     — list of game_keys, each played at least once
#   fragments        — Alchemy fragments found >= N
#   signal_unlocked  — the full Alchemy Signal unlocked
#   minecraft_linked — has a linked Minecraft account
#   peer_insights    — peer feedback given >= N

GEAR = [
    {
        "key": "hydro-router",
        "name": "Hydro-Router Mk I",
        "slot": "tool", "rarity": "standard", "icon": "⟠",
        "flavor": "Keel-made from reclaimed pipe metal. Routes 40 units a minute, complains the whole time.",
        "hint": "Run the Flow Control sim once.",
        "needs": {"games_played": ["flow-control"]},
    },
    {
        "key": "broker-cipher-key",
        "name": "Broker Cipher Key",
        "slot": "tool", "rarity": "epic", "icon": "⌗",
        "flavor": "Cut from a toll collector's badge. The Brokers' own words, turned against the tollbooth.",
        "hint": "Signal Decrypt personal best of 800 or higher.",
        "needs": {"game_best": ["signal-decrypt", 800]},
    },
    {
        "key": "cartographers-lens",
        "name": "Cartographer's Lens",
        "slot": "visor", "rarity": "standard", "icon": "◉",
        "flavor": "Shows the pipes under the streets. Once you see the system, you can't unsee it.",
        "hint": "Earn the Curiosity Power (B1llbot rewards good questions).",
        "needs": {"powers": ["Curiosity"]},
    },
    {
        "key": "empath-array",
        "name": "Empath Array",
        "slot": "visor", "rarity": "epic", "icon": "◭",
        "flavor": "Reads a room the way the Lens reads pipework. Alpha Dynamics never built one. Couldn't.",
        "hint": "Earn 3 of the 4 Empathetic Changemaker Powers.",
        "needs": {"powers_in": ["Empathetic Changemaker", 3]},
    },
    {
        "key": "cistern-core",
        "name": "Cistern Core",
        "slot": "pack", "rarity": "epic", "icon": "⬢",
        "flavor": "A reserve you wear. Heavy on day one, weightless the day the pipe bursts.",
        "hint": "Reach Level 3 and post a Flow Control score of 250+.",
        "needs": {"level": 3, "game_best": ["flow-control", 250]},
    },
    {
        "key": "signal-triangulator",
        "name": "Signal Triangulator",
        "slot": "pack", "rarity": "epic", "icon": "⟁",
        "flavor": "Three points define a source. It's humming toward something.",
        "hint": "…it activates at three. Three of what? Keep looking.",
        "secret": True,
        "needs": {"fragments": 3},
    },
    {
        "key": "a-antenna",
        "name": "A's Antenna",
        "slot": "relic", "rarity": "legendary", "icon": "⬡",
        "flavor": "It only ever receives. Origin unresolved. The channel stays open — you earned that.",
        "hint": "SIGNAL LOCKED.",
        "secret": True,
        "needs": {"signal_unlocked": True},
    },
    {
        "key": "basin-treads",
        "name": "Basin Treads",
        "slot": "boots", "rarity": "standard", "icon": "⛶",
        "flavor": "Mud from all three tiers of the mountain, ground into the soles. That's the point.",
        "hint": "Link a Minecraft account and log one Basin quest.",
        "needs": {"minecraft_linked": True, "quests": 1},
    },
    {
        "key": "collaborators-band",
        "name": "Collaborator's Band",
        "slot": "band", "rarity": "standard", "icon": "◍",
        "flavor": "Woven from four different cords. None of them load-bearing alone.",
        "hint": "Give peer feedback on classmates' work (3 insights).",
        "needs": {"peer_insights": 3},
    },
    {
        "key": "first-drop-vial",
        "name": "First Drop Vial",
        "slot": "relic", "rarity": "standard", "icon": "◌",
        "flavor": "Water from the first cycle the pipes ran again. Everyone who was there got one.",
        "hint": "Complete 2 missions — be part of making the water move.",
        "needs": {"missions": 2},
    },
    {
        "key": "keel-guardian-plate",
        "name": "Keel Guardian Plate",
        "slot": "armor", "rarity": "epic", "icon": "▣",
        "flavor": "Stamped with the town seal. Not armor against people — armor for them.",
        "hint": "Reach Level 8: Keel Guardian.",
        "needs": {"level": 8},
    },
    {
        "key": "legends-sigil",
        "name": "Legend's Sigil",
        "slot": "relic", "rarity": "legendary", "icon": "✦",
        "flavor": "All four Qualities, one bearer. The network tells stories about agents like this.",
        "hint": "Earn all 4 Superpower badges in full.",
        "needs": {"qualities": 4},
    },
]

GEAR_BY_KEY = {g["key"]: g for g in GEAR}


def evaluate_gear(facts: dict) -> list:
    """facts: {level, missions, quests, powers_earned (set), quality_counts
    (dict quality->earned count), qualities_earned (int), game_best (dict
    game->best), games_played (set), fragments (int), signal_unlocked
    (bool), minecraft_linked (bool), peer_insights (int)}.
    Returns the catalog annotated with unlocked flags."""
    out = []
    for item in GEAR:
        needs = item["needs"]
        ok = True
        if "level" in needs and facts.get("level", 1) < needs["level"]:
            ok = False
        if "missions" in needs and facts.get("missions", 0) < needs["missions"]:
            ok = False
        if "quests" in needs and facts.get("quests", 0) < needs["quests"]:
            ok = False
        if "powers" in needs and not set(needs["powers"]) <= facts.get("powers_earned", set()):
            ok = False
        if "powers_in" in needs:
            quality, n = needs["powers_in"]
            if facts.get("quality_counts", {}).get(quality, 0) < n:
                ok = False
        if "qualities" in needs and facts.get("qualities_earned", 0) < needs["qualities"]:
            ok = False
        if "game_best" in needs:
            game, score = needs["game_best"]
            if facts.get("game_best", {}).get(game, 0) < score:
                ok = False
        if "games_played" in needs and not set(needs["games_played"]) <= facts.get("games_played", set()):
            ok = False
        if "fragments" in needs and facts.get("fragments", 0) < needs["fragments"]:
            ok = False
        if "signal_unlocked" in needs and not facts.get("signal_unlocked"):
            ok = False
        if "minecraft_linked" in needs and not facts.get("minecraft_linked"):
            ok = False
        if "peer_insights" in needs and facts.get("peer_insights", 0) < needs["peer_insights"]:
            ok = False

        out.append({
            "key": item["key"], "name": item["name"], "slot": item["slot"],
            "rarity": item["rarity"], "icon": item["icon"],
            "flavor": item["flavor"],
            "hint": None if (item.get("secret") and not ok) else item["hint"],
            "secret": bool(item.get("secret")),
            "unlocked": ok,
        })
    return out
