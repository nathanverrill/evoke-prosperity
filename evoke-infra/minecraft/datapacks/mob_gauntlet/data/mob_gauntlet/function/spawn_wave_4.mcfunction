title @a[distance=..100] title {"text":"Wave 4","color":"gray"}
execute at @e[tag=marker.spawn, sort=random, limit=6] run summon minecraft:blaze ~ ~ ~ {Size:3, Tags:["mob.wave"], DeathLootTable:""}
execute at @e[tag=marker.spawn, sort=random, limit=7] run summon minecraft:wither_skeleton ~ ~ ~ {Tags:["mob.wave"], DeathLootTable:""}
execute at @e[tag=marker.spawn, sort=random, limit=4] run summon minecraft:magma_cube ~ ~ ~ {Size:3, Tags:["mob.wave"], DeathLootTable:""}
