title @a[distance=..100] title {"text":"Wave 6","color":"gray"}
execute at @e[tag=marker.spawn, sort=random, limit=10] run summon minecraft:pillager ~ ~ ~ {Size:3, Tags:["mob.wave"], DeathLootTable:""}
execute at @e[tag=marker.spawn, sort=random, limit=6] run summon minecraft:stray ~ ~ ~ {Size:3, Tags:["mob.wave"], DeathLootTable:""}
execute at @e[tag=marker.spawn, sort=random, limit=1] run summon minecraft:ravager ~ ~ ~ {Size:3, Tags:["mob.wave"], DeathLootTable:""}
