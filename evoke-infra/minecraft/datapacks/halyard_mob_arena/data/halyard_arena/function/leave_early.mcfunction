# Called (as the player) when tick.mcfunction notices someone flagged
# arenaActive=1 who is no longer inside the room bounds -- either they
# walked back out the door without dying/winning, or they disconnected
# mid-run and this is catching them on reconnect (they'd have respawned
# outside the box). Either way, release the lock instead of leaving the
# arena stuck for the next player.
tellraw @s {"text":"Your arena run ended early.","color":"gray"}
scoreboard players set @s arenaActive 0
scoreboard players set @s arenaWave 0
scoreboard players set #global arenaOccupied 0
kill @e[tag=arena_mob]
