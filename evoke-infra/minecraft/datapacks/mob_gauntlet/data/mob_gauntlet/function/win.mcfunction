tellraw @a[distance=..100] {"text":"You survived the Mob Gauntlet. All seven waves, giants included.","color":"green","bold":true}
title @a[distance=..100] title {"text":"Thanks for playing...","color":"green"}
kill @e[tag=mob.wave]
kill @e[tag=marker.spawn]
scoreboard players set #global gauntlet.active 0
scoreboard players set #global gauntlet.wave 0
scoreboard players set #global gauntlet.countdown 0
