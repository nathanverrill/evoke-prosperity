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

# Self-heal (walked out without dying/winning, or reconnected after a
# mid-run disconnect and respawned elsewhere): an active player who is no
# longer inside the room bounds gets their run closed out here instead of
# staying stuck -- also covers a stale arenaActive from the disconnect case
# below, since a reconnecting player gets caught by this the moment they're
# next seen outside the box.
execute as @a[scores={arenaActive=1}] unless entity @s[x=-37,y=69,z=89,dx=14,dy=10,dz=14] run function halyard_arena:leave_early

# Self-heal (disconnected mid-run and hasn't reconnected yet): nobody
# online currently has an active run, but the room is still marked
# occupied -- release the global lock so other players aren't blocked
# while we wait for that player to come back (they'll get caught by the
# rule above once they do).
execute if score #global arenaOccupied matches 1 unless entity @a[scores={arenaActive=1}] run scoreboard players set #global arenaOccupied 0
