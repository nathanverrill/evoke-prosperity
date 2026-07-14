# Original command block at 305,133,-143; see lane1.mcfunction.
scoreboard players add rail2 cartTimer 1
execute if score rail2 cartTimer matches 80 run summon minecraft:chest_minecart 305 131 -143
execute if score rail2 cartTimer matches 80.. run scoreboard players set rail2 cartTimer 0
