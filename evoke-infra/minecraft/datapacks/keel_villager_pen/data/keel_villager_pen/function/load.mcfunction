# The starter villager pen -- "the NPC villagers at the start" per
# MINECRAFT_WORLD_MAP.md, right next to Billbot's kiosk.
#
# chuzz and Fredster are NOT summoned here anymore (found 2026-07-21: real,
# organically-named villagers already existed at these exact recovered
# coordinates -- someone had name-tagged them in actual gameplay, full AI,
# damageable. This datapack used to summon a decorative NoAI/Invulnerable
# copy directly on top of each, and the two overlapping nameplates produced
# garbled text in-game. Per decision: keep the real originals, stop
# resummoning decorative duplicates over them. Their real AI means they can
# wander -- npcs.json's fixed x/y/z for chat proximity may drift out of
# sync with their actual position over time as a result.
#
# Ethan had no such real duplicate, so he's still summoned normally.
#
# Idempotent via a persistent command-storage flag, not an "unless entity"
# check -- entity-existence checks race against forceloaded-chunk timing
# at boot (the #minecraft:load tag fires before forceloaded chunks are
# actually populated for @e to see) and produced duplicates on restart
# even with forceload active. Storage loads synchronously with world data,
# no such race.
forceload add -25 183

execute unless data storage keel_villager_pen:state {ethan:1b} run summon villager -25.5 65 183.7 {Tags:["keel_pen_ethan"],CustomName:"Ethan",CustomNameVisible:1b,PersistenceRequired:1b,NoAI:1b,Invulnerable:1b,VillagerData:{profession:"minecraft:none",level:1,type:"minecraft:desert"}}
data modify storage keel_villager_pen:state ethan set value 1b
