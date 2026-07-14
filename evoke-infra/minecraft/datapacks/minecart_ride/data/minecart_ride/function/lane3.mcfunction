# Original command block at 306,133,-144; see lane1.mcfunction.
scoreboard players add rail3 cartTimer 1
execute if score rail3 cartTimer matches 80 run summon minecraft:chest_minecart 306 131 -144
execute if score rail3 cartTimer matches 80.. run scoreboard players set rail3 cartTimer 0
