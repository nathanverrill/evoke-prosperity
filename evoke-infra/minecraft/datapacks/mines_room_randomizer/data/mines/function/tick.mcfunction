# Occupancy detection for all 4 rooms, using the safe if/unless
# complementary pattern throughout (room00/room01 already used this on the
# live world; room10/room11 originally paired an unconditional "set 1"
# with a conditional "set 0", correct only if two independent repeating
# command blocks happened to tick in a specific, Mojang-unguaranteed
# order -- fixed live via RCON in the 2026-07-14 pass, carried forward
# here).
execute if entity @a[x=-137,y=27,z=-91,dx=14,dy=22,dz=31] run scoreboard players set room00 room 0
execute unless entity @a[x=-137,y=27,z=-91,dx=14,dy=22,dz=31] run scoreboard players set room00 room 1

execute if entity @a[x=-137,y=27,z=-122,dx=14,dy=22,dz=31] run scoreboard players set room10 room 0
execute unless entity @a[x=-137,y=27,z=-122,dx=14,dy=22,dz=31] run scoreboard players set room10 room 1

execute if entity @a[x=-110,y=27,z=-90,dx=14,dy=22,dz=31] run scoreboard players set room01 room 0
execute unless entity @a[x=-110,y=27,z=-90,dx=14,dy=22,dz=31] run scoreboard players set room01 room 1

execute if entity @a[x=-109,y=28,z=-120,dx=14,dy=22,dz=31] run scoreboard players set room11 room 0
execute unless entity @a[x=-109,y=28,z=-120,dx=14,dy=22,dz=31] run scoreboard players set room11 room 1
