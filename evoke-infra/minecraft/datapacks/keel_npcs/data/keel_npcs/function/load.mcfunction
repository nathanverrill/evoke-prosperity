# Visible presence for the chat-only billbot.jar NPC. Jim/Beth/Benjamin/Craig
# are on hold for now (see git history to restore) -- just Billbot for this
# playtest. Idempotent (tag-checked) so a restart never re-summons duplicates.
#
# Invulnerable:1b: Adventure mode blocks block-break/place but NOT attacking
# entities, so without this a player can punch him to death.
#
# Billbot: an "abandoned mining operations robot" per his canon prompt.
# Copper golem over iron golem -- it's passive/non-combat by vanilla design
# (its whole purpose is sorting items, not fighting) and reads more like a
# mechanism than iron golem's "stone guardian" silhouette. weather_state
# + next_weather_age:-2 permanently waxes it so it never oxidizes into a
# frozen statue pose.
execute unless entity @e[type=copper_golem,tag=keel_npc_billbot] run summon copper_golem -49 65 208 {Tags:["keel_npc_billbot"],CustomName:'{"text":"Billbot"}',CustomNameVisible:1b,PersistenceRequired:1b,Silent:1b,NoAI:1b,Invulnerable:1b,weather_state:unaffected,next_weather_age:-2}
