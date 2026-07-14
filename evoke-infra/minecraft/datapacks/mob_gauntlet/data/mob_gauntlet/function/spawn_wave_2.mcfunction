title @a[distance=..100] title {"text":"Wave 2","color":"gray"}
execute at @e[tag=marker.spawn, sort=random, limit=15] run summon minecraft:silverfish ~ ~ ~ {Tags:["mob.wave"], DeathLootTable:""}
