# Runs every 100 ticks (5s) from tick.mcfunction. Ported from true_oasis's
# raw command blocks at (40-41,89,104) [town grant + cap] and
# (324-329,118,-150..-153) [factory drain, warnings, ejection]. Creative
# players exempt from drain/ejection, matching the original's selectors.

# Halyard town grants time: +1 level per cycle, capped at 60.
xp add @a[x=-26,y=92,z=52,dx=137,dy=30,dz=138,level=..59,gamemode=!creative] 1 levels
xp set @a[x=-26,y=92,z=52,dx=137,dy=30,dz=138,level=61..,gamemode=!creative] 60 levels

# The factory floor costs time: -1 level per cycle.
xp add @a[x=295,y=118,z=-154,dx=38,dy=16,dz=43,gamemode=!creative,level=1..] -1 levels

# Warnings, then ejection to the Halyard plaza at zero.
title @a[x=295,y=118,z=-154,dx=38,dy=16,dz=43,gamemode=!creative,level=2..5] actionbar {"text":"Time to go!","color":"gold"}
title @a[x=295,y=118,z=-154,dx=38,dy=16,dz=43,gamemode=!creative,level=1] actionbar {"text":"I warned you!","color":"red"}
execute as @a[x=295,y=118,z=-154,dx=38,dy=16,dz=43,gamemode=!creative,level=0] run tellraw @s {"text":"Shift's over. Come back when you've saved up more time.","color":"red"}
tp @a[x=295,y=118,z=-154,dx=38,dy=16,dz=43,gamemode=!creative,level=0] 6 94 98

# Entry-pad guidance: standing at the pad without enough time saved.
title @a[x=0,y=91,z=96,dx=5,dy=3,dz=5,level=..59,gamemode=!creative] actionbar {"text":"The factory needs 60 levels of saved time -- wait in Halyard to build it up.","color":"gray"}
