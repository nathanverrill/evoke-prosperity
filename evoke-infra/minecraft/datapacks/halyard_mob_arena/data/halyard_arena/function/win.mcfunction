# Called (as the player) once wave 5 is cleared -- next_wave.mcfunction
# already bumped arenaWave to 6 before dispatching here.
tellraw @s {"text":"You survived the Halyard Mob Arena. Five waves, still standing.","color":"green","bold":true}
scoreboard players add @s money 250
tellraw @s [{"text":"+250 money -- balance: ","color":"gold"},{"score":{"name":"@s","objective":"money"}}]

scoreboard players set @s arenaActive 0
scoreboard players set @s arenaWave 0
scoreboard players set #global arenaOccupied 0
kill @e[tag=arena_mob]
tp @s -30 71 87
