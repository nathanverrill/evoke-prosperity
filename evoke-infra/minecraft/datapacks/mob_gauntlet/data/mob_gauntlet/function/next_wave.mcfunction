# Credit everyone nearby with clearing the wave that just ended, before it
# increments below -- skipped on the very first call (gauntlet.wave still
# 0, nothing cleared yet). Ratcheted the same way arenaBestWave is, so a
# repeat clear of an already-recorded wave never re-grants XP.
execute if score #global gauntlet.wave matches 1.. as @a[distance=..100] if score @s gauntletBestWave < #global gauntlet.wave run scoreboard players operation @s gauntletBestWave = #global gauntlet.wave

scoreboard players add #global gauntlet.wave 1
execute if score #global gauntlet.wave matches 8.. run function mob_gauntlet:win
execute unless score #global gauntlet.wave matches 8.. run function mob_gauntlet:refresh_markers

execute if score #global gauntlet.wave matches 1 run function mob_gauntlet:spawn_wave_1
execute if score #global gauntlet.wave matches 2 run function mob_gauntlet:spawn_wave_2
execute if score #global gauntlet.wave matches 3 run function mob_gauntlet:spawn_wave_3
execute if score #global gauntlet.wave matches 4 run function mob_gauntlet:spawn_wave_4
execute if score #global gauntlet.wave matches 5 run function mob_gauntlet:spawn_wave_5
execute if score #global gauntlet.wave matches 6 run function mob_gauntlet:spawn_wave_6
execute if score #global gauntlet.wave matches 7 run function mob_gauntlet:spawn_wave_7
