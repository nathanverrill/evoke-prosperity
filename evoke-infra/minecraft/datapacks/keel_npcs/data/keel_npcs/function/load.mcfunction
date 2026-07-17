# Visible presence for the chat-only billbot.jar NPCs -- these villagers
# have no functional trades, they're purely a body to stand next to while
# the mod's proximity chat handles the actual conversation. Idempotent
# (tag-checked) so a restart never re-summons duplicates.
#
# Invulnerable:1b on all 5: Adventure mode blocks block-break/place but NOT
# attacking entities, so without this a player can punch any of them to death.
execute unless entity @e[type=villager,tag=keel_npc_jim] run summon villager -140 66 170 {Tags:["keel_npc_jim"],CustomName:'{"text":"Jim"}',CustomNameVisible:1b,PersistenceRequired:1b,Silent:1b,NoAI:1b,Invulnerable:1b,VillagerData:{profession:"minecraft:mason",level:1,type:"minecraft:plains"}}

execute unless entity @e[type=villager,tag=keel_npc_beth] run summon villager -47 69 158 {Tags:["keel_npc_beth"],CustomName:'{"text":"Beth"}',CustomNameVisible:1b,PersistenceRequired:1b,Silent:1b,NoAI:1b,Invulnerable:1b,VillagerData:{profession:"minecraft:mason",level:1,type:"minecraft:plains"}}

execute unless entity @e[type=villager,tag=keel_npc_benjamin] run summon villager -63 65 205 {Tags:["keel_npc_benjamin"],CustomName:'{"text":"Benjamin"}',CustomNameVisible:1b,PersistenceRequired:1b,Silent:1b,NoAI:1b,Invulnerable:1b,VillagerData:{profession:"minecraft:toolsmith",level:1,type:"minecraft:plains"}}

execute unless entity @e[type=villager,tag=keel_npc_craig] run summon villager -68 65 218 {Tags:["keel_npc_craig"],CustomName:'{"text":"Craig"}',CustomNameVisible:1b,PersistenceRequired:1b,Silent:1b,NoAI:1b,Invulnerable:1b,VillagerData:{profession:"minecraft:mason",level:1,type:"minecraft:plains"}}

# Billbot: an "abandoned mining operations robot" per his canon prompt.
# Copper golem over iron golem -- it's passive/non-combat by vanilla design
# (its whole purpose is sorting items, not fighting) and reads more like a
# mechanism than iron golem's "stone guardian" silhouette. weather_state
# + next_weather_age:-2 permanently waxes it so it never oxidizes into a
# frozen statue pose.
execute unless entity @e[type=copper_golem,tag=keel_npc_billbot] run summon copper_golem -49 65 208 {Tags:["keel_npc_billbot"],CustomName:'{"text":"Billbot"}',CustomNameVisible:1b,PersistenceRequired:1b,Silent:1b,NoAI:1b,Invulnerable:1b,weather_state:unaffected,next_weather_age:-2}
