title @a[distance=..100] title {"text":"Wave 7 (Final Wave)","color":"gray"}
execute at @e[tag=marker.spawn, sort=random, limit=12] run summon minecraft:ravager ~ ~ ~ {Size:3, Tags:["mob.wave"], DeathLootTable:""}
execute at @e[tag=marker.spawn, sort=random, limit=16] run summon minecraft:zombie ~ ~ ~ {IsBaby:1, Size:3, Tags:["mob.wave"], DeathLootTable:""}
