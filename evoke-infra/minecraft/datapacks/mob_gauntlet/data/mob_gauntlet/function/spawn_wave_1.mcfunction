title @a[distance=..100] title {"text":"Wave 1","color":"gray"}
execute at @e[tag=marker.spawn, sort=random, limit=5] run summon husk ~ ~ ~ {Tags:["mob.wave"], DeathLootTable:"minecraft:entities/husk"}
