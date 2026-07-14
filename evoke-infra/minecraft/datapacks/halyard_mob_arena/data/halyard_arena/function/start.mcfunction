# Called (as the entering player) when tick.mcfunction detects someone on
# the entry plate, the arena is unoccupied, and they're not already in a run.
scoreboard players set #global arenaOccupied 1
scoreboard players set @s arenaActive 1
scoreboard players set @s arenaWave 0
scoreboard players operation @s arenaLastDeaths = @s arenaDeaths

# Safety sweep -- clear any leftover arena_mob from an interrupted prior run
# before this one starts.
kill @e[tag=arena_mob]

tellraw @s {"text":"CLAUDE'S HALYARD MOB ARENA","color":"dark_red","bold":true}
tellraw @s {"text":"Waves get harder. Spider eyes drop from every kill -- sell them outside for money. Die, and whatever you're carrying when you go down stays here.","color":"gray"}
tp @s -30 71 96
function halyard_arena:next_wave
