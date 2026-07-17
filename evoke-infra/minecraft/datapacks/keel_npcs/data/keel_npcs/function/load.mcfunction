# Visible presence for the chat-only billbot.jar NPCs -- these villagers
# have no functional trades, they're purely a body to stand next to while
# the mod's proximity chat handles the actual conversation. Idempotent
# (tag-checked) so a restart never re-summons duplicates.
execute unless entity @e[type=villager,tag=keel_npc_jim] run summon villager -140 66 170 {Tags:["keel_npc_jim"],CustomName:'{"text":"Jim"}',CustomNameVisible:1b,PersistenceRequired:1b,Silent:1b,NoAI:1b,VillagerData:{profession:"minecraft:mason",level:1,type:"minecraft:plains"}}

execute unless entity @e[type=villager,tag=keel_npc_beth] run summon villager -47 69 158 {Tags:["keel_npc_beth"],CustomName:'{"text":"Beth"}',CustomNameVisible:1b,PersistenceRequired:1b,Silent:1b,NoAI:1b,VillagerData:{profession:"minecraft:mason",level:1,type:"minecraft:plains"}}

execute unless entity @e[type=villager,tag=keel_npc_benjamin] run summon villager -63 65 205 {Tags:["keel_npc_benjamin"],CustomName:'{"text":"Benjamin"}',CustomNameVisible:1b,PersistenceRequired:1b,Silent:1b,NoAI:1b,VillagerData:{profession:"minecraft:toolsmith",level:1,type:"minecraft:plains"}}

execute unless entity @e[type=villager,tag=keel_npc_craig] run summon villager -68 65 218 {Tags:["keel_npc_craig"],CustomName:'{"text":"Craig"}',CustomNameVisible:1b,PersistenceRequired:1b,Silent:1b,NoAI:1b,VillagerData:{profession:"minecraft:mason",level:1,type:"minecraft:plains"}}

# Billbot: an "abandoned mining operations robot" per his canon prompt --
# an iron golem fits that lore far better than a villager would.
execute unless entity @e[type=iron_golem,tag=keel_npc_billbot] run summon iron_golem -49 65 208 {Tags:["keel_npc_billbot"],CustomName:'{"text":"Billbot"}',CustomNameVisible:1b,PersistenceRequired:1b,Silent:1b,NoAI:1b}
