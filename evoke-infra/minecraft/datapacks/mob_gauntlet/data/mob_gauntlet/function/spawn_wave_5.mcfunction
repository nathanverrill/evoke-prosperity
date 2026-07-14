title @a[distance=..100] title {"text":"Wave 5","color":"gray"}
execute at @e[tag=marker.spawn, sort=random, limit=16] run summon minecraft:piglin_brute ~ ~ ~ {Size:3, Tags:["mob.wave"], DeathLootTable:""}
