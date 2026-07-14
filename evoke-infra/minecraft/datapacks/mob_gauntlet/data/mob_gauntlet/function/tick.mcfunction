# Entry: anyone on the plate outside the room, not already running, starts
# a shared run for everyone nearby -- this arena was built co-op (titles and
# safety checks all target @a[distance=..100] in the source, not a single
# player), unlike the solo Halyard Mob Arena.
execute as @a[x=400,y=141,z=777,distance=..1] if score #global gauntlet.active matches 0 run function mob_gauntlet:start

execute if score #global gauntlet.active matches 1 run function mob_gauntlet:run
