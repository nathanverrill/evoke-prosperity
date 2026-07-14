# Nobody within 50 blocks of the room -- stop the run instead of leaving
# wave mobs (potentially giant ones) alive and wandering indefinitely.
execute if score #global gauntlet.active matches 1 run kill @e[tag=mob.wave]
execute if score #global gauntlet.active matches 1 run kill @e[tag=marker.spawn]
scoreboard players set #global gauntlet.active 0
scoreboard players set #global gauntlet.wave 0
scoreboard players set #global gauntlet.countdown 0
