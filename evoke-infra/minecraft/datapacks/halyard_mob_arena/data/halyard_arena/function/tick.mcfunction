# Entry: standing on the plate outside the door, not already in a run, and
# nobody else currently occupying the room (v1 is solo -- one run at a time).
execute as @a[x=-30,y=70,z=89,distance=..1] unless score @s arenaActive matches 1 if score #global arenaOccupied matches 0 run function halyard_arena:start

# Sell: standing on the sell plate just outside the entrance.
execute as @a[x=-28,y=70,z=89,distance=..1] run function halyard_arena:sell

# Wave clear -- only for the player currently in an active run, and only
# once the room is empty of arena_mob.
execute as @a[scores={arenaActive=1,arenaWave=1..5}] if entity @s unless entity @e[tag=arena_mob] run function halyard_arena:next_wave

# Death -- deathCount (vanilla built-in) ticked up since the snapshot we
# took at the start of this run.
execute as @a[scores={arenaActive=1}] if score @s arenaDeaths > @s arenaLastDeaths run function halyard_arena:on_death
