# 3-2-1 countdown between waves, 20 ticks (1 second) apart -- matches the
# original's exact timing.
scoreboard players add #global gauntlet.countdown 1
execute if score #global gauntlet.countdown matches 1 run title @a[distance=..100] title {"text":"3","color":"green"}
execute if score #global gauntlet.countdown matches 21 run title @a[distance=..100] title {"text":"2","color":"gold"}
execute if score #global gauntlet.countdown matches 41 run title @a[distance=..100] title {"text":"1","color":"red"}
execute if score #global gauntlet.countdown matches 61 run scoreboard players set #global gauntlet.countdown 0
execute if score #global gauntlet.countdown matches 0 run function mob_gauntlet:next_wave
