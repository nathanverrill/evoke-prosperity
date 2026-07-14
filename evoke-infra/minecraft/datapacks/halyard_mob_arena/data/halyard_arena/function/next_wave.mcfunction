# Called as the active player once the room is clear of arena_mob (from
# tick.mcfunction) or right after start.mcfunction for wave 1.
scoreboard players add @s arenaWave 1

execute if score @s arenaWave > @s arenaBestWave run scoreboard players operation @s arenaBestWave = @s arenaWave

execute if score @s arenaWave matches 1 run function halyard_arena:spawn_wave_1
execute if score @s arenaWave matches 2 run function halyard_arena:spawn_wave_2
execute if score @s arenaWave matches 3 run function halyard_arena:spawn_wave_3
execute if score @s arenaWave matches 4 run function halyard_arena:spawn_wave_4
execute if score @s arenaWave matches 5 run function halyard_arena:spawn_wave_5
execute if score @s arenaWave matches 6.. run function halyard_arena:win

execute if score @s arenaWave matches ..5 run tellraw @s [{"text":"Wave ","color":"gold"},{"score":{"name":"@s","objective":"arenaWave"},"color":"gold"},{"text":" of 5","color":"gold"}]
