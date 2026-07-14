# Halyard Mob Arena -- from docs/legacy/All NPC and World Prompts/
# halyard-minigames.txt's original design (never built until now): wave-based
# combat, mobs drop spider eyes, sell them for money (the same vanilla `money`
# scoreboard the rent timer and day-job loop already use -- no new currency).

scoreboard objectives add arenaActive dummy
scoreboard objectives add arenaWave dummy
scoreboard objectives add arenaBestWave dummy
scoreboard objectives add arenaLastDeaths dummy
# deathCount is a built-in vanilla criteria -- auto-increments on every player
# death, no custom on-death detection needed. tick.mcfunction compares this
# against arenaLastDeaths each tick to notice a death happened during a run.
scoreboard objectives add arenaDeaths deathCount

# money/rent/fees already exist (halyard_rent_functions); ensure it's present
# even if this pack ever runs standalone.
scoreboard objectives add money dummy

# arena-wide occupancy lock (fake-player global score, same idiom as
# halyard_rent_functions' #11/#10 constants) -- one run at a time, v1 keeps
# the room simple to verify rather than building multi-instance support.
scoreboard objectives add arenaOccupied dummy
scoreboard players set #global arenaOccupied 0

scoreboard objectives add constants dummy
scoreboard players set #5 constants 5

# scratch objective for the sell function's count * price operation
scoreboard objectives add arenaSellCount dummy
