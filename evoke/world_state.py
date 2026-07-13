"""Collective world-state: Keel's restoration, driven by the whole cohort's
mission completions — GAPS.md's #5 flagged gap ("the single strongest
transmedia glue available"). The story is about Keel recovering; this is
the mechanism that makes the class's combined effort *visible*, on the
Operations Hub (restoration meter) and physically in the Minecraft world
(the Restoration Beacon the bridge builds as stages advance).

Design shape: every distinct (learner, mission) completion anywhere in the
cohort adds one drop to the same shared pool; the pool total maps to a
restoration STAGE (0-8). Stage advances are cohort events, not personal
ones — they fire a WorldStateAdvanced event that celebrates on every
surface at once (Hub banner, activity feed, live toast, in-game titles +
fireworks + a new Beacon layer).

How the stage step is chosen — a knob, with variants (per the Team Wheel
convention in GAME_DESIGN.md §7.1: surface the menu, don't silently pick):

1. **Fixed completions-per-stage (shipped default).** Stage = total
   completions // WORLD_STAGE_STEP. Default step is 2 so a single-learner
   dev box can watch the whole arc; a real cohort sets it via env — e.g.
   a class of 25 doing 12 missions = 300 completions, step 33 ≈ 8 stages
   spread across the campaign. Simple, predictable, tunable per cohort.
2. **Roster-aware fraction.** Stage = f(completions / (roster × 12)) — the
   meter always spans exactly the campaign regardless of class size, but
   roster churn changes past progress (same fixed-denominator problem the
   Team Wheel's variant #1 solves with a rolling snapshot).
3. **Milestone-mission gating.** Stages advance only when specific
   missions complete cohort-wide ("stage 4 = half the class finished
   Mission 6") — tightest narrative sync, most design upkeep.

Shipped: #1, because it needs zero roster knowledge and degrades
gracefully in every classroom size; revisit #2/#3 when a real cohort's
pacing data exists.
"""

import os

# Missions-per-stage knob. Default 2 = demo-friendly (one learner can
# advance the world). A real classroom sets WORLD_STAGE_STEP so the final
# stage lands near campaign end (roster × 12 // 8, roughly).
STAGE_STEP = max(1, int(os.getenv("WORLD_STAGE_STEP", "2")))

# Stage 0 is the world as found — never "achieved", just the floor.
# Titles/narratives are the in-fiction beats every surface displays; the
# bridge renders the *number* (beacon layers), so wording changes here
# never need a bridge redeploy.
STAGES = [
    {"key": "runoff",        "title": "Runoff",                     "narrative": "Keel as the Agents found it — the mountain keeps what it takes."},
    {"key": "first-drops",   "title": "First Drops",                "narrative": "The old pipes shudder awake. Somebody upstairs noticed."},
    {"key": "cisterns",      "title": "The Cisterns Fill",          "narrative": "Keel is saving again — stored water, stored value."},
    {"key": "pumps",         "title": "The Pumps Turn Over",        "narrative": "Alpha Dynamics' abandoned pumps run for the first time in years."},
    {"key": "terraces",      "title": "Water Reaches the Terraces", "narrative": "The gardens come back. Kids race the channels after school."},
    {"key": "market",        "title": "The Market Reopens",         "narrative": "Trade returns to Keel's square — cups on every stall, carved from pipe metal."},
    {"key": "lights",        "title": "Lights on the Mountain",     "narrative": "Halyard notices. The Brokers pretend not to."},
    {"key": "network",       "title": "The Network Hums",           "narrative": "Basin towns connect, node by node. Nobody owns the map."},
    {"key": "water-rises",   "title": "The Water Rises",            "narrative": "Keel prospers. Even the Oasis looks down and wonders how."},
]

MAX_STAGE = len(STAGES) - 1


def stage_for(completions: int) -> int:
    return min(MAX_STAGE, completions // STAGE_STEP)


def stage_meta(stage: int) -> dict:
    stage = max(0, min(MAX_STAGE, stage))
    return {"stage": stage, "total_stages": MAX_STAGE, **STAGES[stage]}
