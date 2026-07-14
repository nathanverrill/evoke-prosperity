# Original command block at 304,133,-142 summoned relative to its own
# position (~ ~-2 ~); hardcoded here since a tick function has no
# meaningful position context of its own.
scoreboard players add rail1 cartTimer 1
execute if score rail1 cartTimer matches 80 run summon minecraft:chest_minecart 304 131 -142
execute if score rail1 cartTimer matches 80.. run scoreboard players set rail1 cartTimer 0
