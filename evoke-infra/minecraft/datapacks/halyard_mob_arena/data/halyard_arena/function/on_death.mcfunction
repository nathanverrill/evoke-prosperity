# Called (as the player) from tick.mcfunction once it notices arenaDeaths
# ticked up while arenaActive=1. Vanilla respawn has already moved them by
# the time this runs -- this just closes out the run and the stakes.
tellraw @s {"text":"You went down in the arena. Whatever you were carrying stays there.","color":"red"}

# The real stake: anything dropped on death (spider eyes included) gets
# swept from the room instead of staying pickable -- "lose unbanked spider
# eyes only" per design; already-sold money is untouched, this is the only
# place currency at risk actually lives.
kill @e[type=item,x=-30,y=73,z=96,dx=13,dy=9,dz=13]
kill @e[tag=arena_mob]

scoreboard players operation @s arenaLastDeaths = @s arenaDeaths
scoreboard players set @s arenaActive 0
scoreboard players set @s arenaWave 0
scoreboard players set #global arenaOccupied 0
tp @s -30 71 85
