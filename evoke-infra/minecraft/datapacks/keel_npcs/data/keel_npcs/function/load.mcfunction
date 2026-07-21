# Visible presence for the chat-only billbot.jar NPCs -- these villagers
# have no functional trades, they're purely a body to stand next to while
# the mod's proximity chat handles the actual conversation. Idempotent
# (tag-checked) so a restart never re-summons duplicates.
#
# Invulnerable:1b: Adventure mode blocks block-break/place but NOT
# attacking entities, so without this a player can punch it to death.

# Billbot: an "abandoned mining operations robot" per his canon prompt.
# Copper golem over iron golem -- it's passive/non-combat by vanilla design
# (its whole purpose is sorting items, not fighting) and reads more like a
# mechanism than iron golem's "stone guardian" silhouette. weather_state
# + next_weather_age:-2 permanently waxes it so it never oxidizes into a
# frozen statue pose.
#
# Idempotent via a persistent command-storage flag, not an "unless entity"
# check -- entity-existence checks race against forceloaded-chunk timing
# at boot (the #minecraft:load tag fires before forceloaded chunks are
# actually populated for @e to see) and produced a duplicate on restart
# even with forceload active. Storage loads synchronously with world data,
# no such race.
forceload add -49 208
execute unless data storage keel_npcs:state {billbot:1b} run summon copper_golem -49 65 208 {Tags:["keel_npc_billbot"],CustomName:"Billbot",CustomNameVisible:1b,PersistenceRequired:1b,Silent:1b,NoAI:1b,Invulnerable:1b,weather_state:unaffected,next_weather_age:-2}
data modify storage keel_npcs:state billbot set value 1b

# The four original Keel townsfolk (restored 2026-07-21) -- ThirdBrain mod
# entities in the original build, removed with that mod for school use;
# re-created here as plain villagers at their original ThirdBrain posts
# (the original npcs.json coordinates). Their conversation is the staged
# npc_lines system, same as Billbot. Same storage-flag idempotency.
forceload add -140 170
execute unless data storage keel_npcs:state {jim:1b} run summon villager -140 66 170 {Tags:["keel_npc_jim"],CustomName:"Jim",CustomNameVisible:1b,PersistenceRequired:1b,Silent:1b,NoAI:1b,Invulnerable:1b,VillagerData:{profession:"minecraft:mason",level:1,type:"minecraft:plains"}}
data modify storage keel_npcs:state jim set value 1b

forceload add -47 158
execute unless data storage keel_npcs:state {beth:1b} run summon villager -47 69 158 {Tags:["keel_npc_beth"],CustomName:"Beth",CustomNameVisible:1b,PersistenceRequired:1b,Silent:1b,NoAI:1b,Invulnerable:1b,VillagerData:{profession:"minecraft:mason",level:1,type:"minecraft:plains"}}
data modify storage keel_npcs:state beth set value 1b

forceload add -63 205
execute unless data storage keel_npcs:state {benjamin:1b} run summon villager -63 65 205 {Tags:["keel_npc_benjamin"],CustomName:"Benjamin",CustomNameVisible:1b,PersistenceRequired:1b,Silent:1b,NoAI:1b,Invulnerable:1b,VillagerData:{profession:"minecraft:toolsmith",level:1,type:"minecraft:plains"}}
data modify storage keel_npcs:state benjamin set value 1b

forceload add -68 218
execute unless data storage keel_npcs:state {craig:1b} run summon villager -68 65 218 {Tags:["keel_npc_craig"],CustomName:"Craig",CustomNameVisible:1b,PersistenceRequired:1b,Silent:1b,NoAI:1b,Invulnerable:1b,VillagerData:{profession:"minecraft:mason",level:1,type:"minecraft:plains"}}
data modify storage keel_npcs:state craig set value 1b
