# Called (as the player) from tick.mcfunction when someone's on the sell
# plate. `clear ... 0` is vanilla's count-only form (maxCount 0 reports the
# match count without removing anything), so this reads the amount before
# actually taking it.
execute store result score @s arenaSellCount run clear @s minecraft:spider_eye 0
execute unless score @s arenaSellCount matches 1.. run return 0

clear @s minecraft:spider_eye
scoreboard players operation @s arenaSellCount *= #5 constants
scoreboard players operation @s money += @s arenaSellCount
tellraw @s [{"text":"Sold spider eyes for +","color":"gold"},{"score":{"name":"@s","objective":"arenaSellCount"}},{"text":" money -- balance: ","color":"gold"},{"score":{"name":"@s","objective":"money"}}]
