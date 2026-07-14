title @a[distance=..100] title {"text":"Wave 3","color":"gray"}
execute at @e[tag=marker.spawn, sort=random, limit=3] run summon minecraft:slime ~ ~ ~ {Size:3, Tags:["mob.wave"], DeathLootTable:""}
execute at @e[tag=marker.spawn, sort=random, limit=4] run summon minecraft:skeleton ~ ~ ~ {Tags:["mob.wave"], DeathLootTable:""}
