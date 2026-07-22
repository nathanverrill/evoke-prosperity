# Original command block at 305,133,-143; see lane1.mcfunction.
# Same cap as lane1 (see lane1.mcfunction's 2026-07-22 incident note).
scoreboard players add rail2 cartTimer 1
execute if score rail2 cartTimer matches 80 store result score #carts cartTimer if entity @e[type=chest_minecart,x=299,y=127,z=-150,dx=14,dy=9,dz=14]
execute if score rail2 cartTimer matches 80 if score #carts cartTimer matches ..5 run summon minecraft:chest_minecart 305 131 -143
execute if score rail2 cartTimer matches 80.. run scoreboard players set rail2 cartTimer 0
