# Original command block at 304,133,-142 summoned relative to its own
# position (~ ~-2 ~); hardcoded here since a tick function has no
# meaningful position context of its own.
# 2026-07-22 incident guard: the lanes summon forever but nothing ever
# removes a cart (no rider, no end-of-track disposal), so ~57k empty carts
# piled up at the spawn post and helped freeze the server. Cap: no lane
# summons while 6+ carts already sit in the shared ride area.
scoreboard players add rail1 cartTimer 1
execute if score rail1 cartTimer matches 80 store result score #carts cartTimer if entity @e[type=chest_minecart,x=299,y=127,z=-150,dx=14,dy=9,dz=14]
execute if score rail1 cartTimer matches 80 if score #carts cartTimer matches ..5 run summon minecraft:chest_minecart 304 131 -142
execute if score rail1 cartTimer matches 80.. run scoreboard players set rail1 cartTimer 0
