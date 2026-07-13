"""World Bank EVOKE Social Innovators' Framework (Freeman & Hawkins, 2016).

Table 1's 4 Qualities and their 16 constituent Powers, verbatim
definitions included. See GAME_DESIGN.md §4/§4.1 for the full citation,
the drift audit against the 12 real missions' Primary/Secondary tags,
and the reasoning behind POWER_ALIASES below -- the missions are fixed
financial-literacy curriculum and cannot be re-tagged, so drift is
resolved here at the interpretation layer instead.
"""

from typing import Optional

QUALITIES = [
    "Creative Visionary",
    "Deep Collaborator",
    "Systems Thinker",
    "Empathetic Changemaker",
]

# Power -> (Quality, verbatim Table 1 definition)
POWERS = {
    "Imagination": ("Creative Visionary", "Presents a unique and new view of the world and imagines a new and better world."),
    "Ideation": ("Creative Visionary", "Commands the World of Ideas: sparks lots of new ideas and reshapes existing ideas."),
    "Vision": ("Creative Visionary", "Envisions the future and is driven to do the difficult work to move a concept to reality."),
    "Courage": ("Creative Visionary", "Ventures into the unknown, showing strength in the face of challenges and willingness to work through the fears and uncertainties of bringing about change."),
    "Communication": ("Deep Collaborator", "Listens, seeks understanding, embraces diverse perspectives, and presents ideas in a compelling way; shows adeptness in relationships."),
    "Teamwork": ("Deep Collaborator", "Gets things done through collaboration with diverse agents, and by building trust and creating effective teams."),
    "Networking": ("Deep Collaborator", "Leverages the power of diverse network resources, making connections by engaging actively and respectfully."),
    "Generosity of Spirit": ("Deep Collaborator", "Collaborates, gives, and shares one's time, ideas and expertise with others."),
    "Problem Solving": ("Systems Thinker", "Takes on unfamiliar problems; questions, analyzes, and experiments with ideas and potential solutions."),
    "Analysis": ("Systems Thinker", "Uses design thinking to reveal systems and illuminate the interconnectedness of problems and solutions."),
    "Aggregation": ("Systems Thinker", "Connects to multiple sources of information and multiple perspectives of people to understand a challenge."),
    "Critical Reflection": ("Systems Thinker", "Questions, analyzes, and considers ideas in light of evidence and feedback."),
    "Leadership": ("Empathetic Changemaker", "Leads the team to accomplish goals by being responsible, flexible yet showing commitment and consistency."),
    "Empathy": ("Empathetic Changemaker", "Walks in others' shoes. Passionate about making a positive difference."),
    "Transformation": ("Empathetic Changemaker", "Inspires and motivates, has a growth mindset, and builds inclusive, diverse, and collaborative teams and networks to create positive and sustainable change in a community."),
    "Curiosity": ("Empathetic Changemaker", "Shows intense curiosity as to how the world works, asks good questions, and listens to answers without judgement."),
}

POWER_TO_QUALITY = {power: quality for power, (quality, _definition) in POWERS.items()}

# Non-canonical tag terms used in the 12 real missions' Primary/Secondary
# fields, aliased to the nearest real Power. See GAME_DESIGN.md §4.1 point 1
# for the reasoning behind each choice (matched against what the mission
# actually asks for, not just word similarity).
POWER_ALIASES = {
    "Research & Analysis": "Aggregation",
    "Creativity": "Ideation",
    "Relationship Management": "Networking",
}

# Powers with zero coverage in the 12 missions' Primary/Secondary tags
# (verified against the real seeded tag data in
# brightspace-sim/brightspace_api.py) -- unlocked by a behavioral trigger
# instead of a mission tag. See GAME_DESIGN.md §4.1's coverage table.
BEHAVIORAL_POWERS = {
    "Generosity of Spirit": {"threshold": 3, "metric": "peer_insights_given"},
    "Curiosity": {"threshold": 10, "metric": "billbot_messages_sent"},
    # Transformation via the daily Field Report (reflection) habit --
    # "has a growth mindset... to create positive and sustainable change":
    # sustained reflection over time is the observable behavior. Approved
    # by Nathan (July 13) as part of the Words of Wisdom mechanic.
    "Transformation": {"threshold": 10, "metric": "daily_reflections"},
    # Analysis remains deferred until the team-reflection mechanic (§7.3)
    # it depends on is built.
}


def resolve_power(tag: Optional[str]) -> Optional[str]:
    """Resolve a mission's raw Primary/Secondary tag to a canonical Power
    name, applying POWER_ALIASES. Returns None for a blank tag or a term
    that resolves to neither a known Power nor a known alias (fails safe
    rather than crediting an achievement for an unrecognized tag)."""
    if not tag:
        return None
    canonical = POWER_ALIASES.get(tag, tag)
    return canonical if canonical in POWER_TO_QUALITY else None
