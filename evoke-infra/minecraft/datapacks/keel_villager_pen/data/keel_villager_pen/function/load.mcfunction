# The starter villager pen -- "the NPC villagers at the start" per
# MINECRAFT_WORLD_MAP.md, right next to Billbot's kiosk. Positions are the
# real recovered coordinates from the world save's own entity NBT
# (basin/entities/r.-1.0.mca), not guessed -- unemployed desert villagers,
# same as the original. Idempotent (tag-checked) so a restart never
# re-summons duplicates. Invulnerable:1b for the same reason keel_npcs
# needs it: Adventure mode blocks block-break/place but not attacking
# entities.
execute unless entity @e[type=villager,tag=keel_pen_chuzz] run summon villager -31.5 65 183.5 {Tags:["keel_pen_chuzz"],CustomName:'{"text":"chuzz"}',CustomNameVisible:1b,PersistenceRequired:1b,NoAI:1b,Invulnerable:1b,VillagerData:{profession:"minecraft:none",level:1,type:"minecraft:desert"}}

execute unless entity @e[type=villager,tag=keel_pen_ethan] run summon villager -25.5 65 183.7 {Tags:["keel_pen_ethan"],CustomName:'{"text":"Ethan"}',CustomNameVisible:1b,PersistenceRequired:1b,NoAI:1b,Invulnerable:1b,VillagerData:{profession:"minecraft:none",level:1,type:"minecraft:desert"}}

execute unless entity @e[type=villager,tag=keel_pen_fredster] run summon villager -22.5 65 199.5 {Tags:["keel_pen_fredster"],CustomName:'{"text":"Fredster"}',CustomNameVisible:1b,PersistenceRequired:1b,NoAI:1b,Invulnerable:1b,VillagerData:{profession:"minecraft:none",level:1,type:"minecraft:desert"}}
