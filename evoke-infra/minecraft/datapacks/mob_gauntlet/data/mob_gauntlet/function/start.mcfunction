scoreboard players set #global gauntlet.active 1
scoreboard players set #global gauntlet.wave 0
scoreboard players set #global gauntlet.countdown 0
kill @e[tag=mob.wave]
kill @e[tag=marker.spawn]
tellraw @a[distance=..100] {"text":"THE MOB GAUNTLET","color":"dark_red","bold":true}
tellraw @a[distance=..100] {"text":"Seven waves. Giants among them. Stay together.","color":"gray"}
function mob_gauntlet:next_wave
