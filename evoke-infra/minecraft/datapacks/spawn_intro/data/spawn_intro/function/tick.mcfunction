# One-shot per player (spawn_intro_done tag): place them on the summit
# facing south over the town (yaw 0 = south, slight downward pitch), ask
# them to look around, then to descend. Runs every 2 ticks; new joiners
# get caught within a tick of appearing.
execute as @a[tag=!spawn_intro_done] run tp @s -34.5 197.0 -31.5 0 15
execute as @a[tag=!spawn_intro_done] run title @s times 10 100 20
execute as @a[tag=!spawn_intro_done] run title @s title {"text":"Take it all in","color":"aqua"}
execute as @a[tag=!spawn_intro_done] run title @s subtitle {"text":"Look around from the summit","color":"white"}
execute as @a[tag=!spawn_intro_done] run tellraw @s [{"text":"You wake at the top of the mountain. ","color":"aqua"},{"text":"Turn slowly and take in the whole basin below — the town, the rooftops, the roads out. When you are ready, make your way down the south slope into town.","color":"white"}]
tag @a[tag=!spawn_intro_done] add spawn_intro_done

schedule function spawn_intro:tick 2t replace
