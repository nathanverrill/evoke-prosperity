"""XP curve and Agent rank titles — the levels-do-something half of GAPS.md's
"XP economy is undesigned" item. Levels 1-10 keep the exact thresholds
overview.md's example table already established (and workers.py already
shipped), extended two steps at the same quadratic-ish cadence so the
campaign has headroom; each level now carries a named Agent rank, announced
on level-up (web celebration + Minecraft title broadcast via LevelUpped).

The values are a playable default, not a settled economy — the per-action
XP amounts still live where they always did (main.py's publish sites) and
GAPS.md still tracks the full economy design as open. What this module
settles is only the shape: thresholds in one place, and a rank name per
level so the number buys an identity, not just a bigger number.
"""

# Level N is reached at THRESHOLDS[N-1] XP. Levels 1-10 match the
# overview.md example table verbatim (see workers.py's original
# xp_to_level); 11-12 continue the same widening-gap cadence.
THRESHOLDS = [0, 100, 250, 450, 700, 1000, 1350, 1750, 2200, 2700, 3250, 3850]

# In-fiction Agent ranks, one per level. Early ranks are generic
# agency-speak; later ones are earned Basin identity (Keel, the network,
# Alchemy) — the title itself tells the story of how far in you are.
RANK_TITLES = [
    "Recruit",              # 1
    "Field Agent",          # 2
    "Operative",            # 3
    "Specialist",           # 4
    "Pathfinder",           # 5
    "Signal Runner",        # 6
    "Basin Veteran",        # 7
    "Keel Guardian",        # 8
    "Flow Engineer",        # 9
    "Network Architect",    # 10
    "Alchemy's Peer",       # 11
    "Legend of the Basin",  # 12
]


def xp_to_level(xp: int) -> int:
    level = 1
    for i, t in enumerate(THRESHOLDS):
        if xp >= t:
            level = i + 1
    return level


def level_title(level: int) -> str:
    if level < 1:
        level = 1
    if level > len(RANK_TITLES):
        level = len(RANK_TITLES)
    return RANK_TITLES[level - 1]


def next_threshold(xp: int):
    """XP needed for the next level, or None at the cap."""
    for t in THRESHOLDS:
        if t > xp:
            return t
    return None
