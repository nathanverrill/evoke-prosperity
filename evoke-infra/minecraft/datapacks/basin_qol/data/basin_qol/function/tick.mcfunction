# Runs every 2 ticks (self-scheduling; armed by basin_qol:load).
# Every mechanic below is a port of raw command blocks found in
# servers/playtest/true_oasis, coordinates preserved exactly.

# --- Mines: void rescue (fell through the world under the mine rooms) ---
# Original: tp box at y=-1 + regeneration + FallDistance reset. Box
# deepened to y=-30..5 so fast fallers can't pass through the plane
# between checks.
execute as @a[x=-131,y=-30,z=-114,dx=24,dy=35,dz=103] run effect give @s minecraft:regeneration 10 4 true
tp @a[x=-131,y=-30,z=-114,dx=24,dy=35,dz=103] -113 66 37

# --- Mines: no fall damage anywhere in the mine complex ---
execute as @a[x=-136,y=-2,z=-122,dx=37,dy=25,dz=110] run data merge entity @s {FallDistance:0f}

# --- Mines: repair station by the entrance (-138..-134, 60..63, 164..168)
# Holding any tier of pickaxe there refreshes it to full durability, one
# command per tier, same as the original's four command blocks.
execute as @a[x=-138,y=60,z=164,dx=4,dy=3,dz=4] at @s if items entity @s weapon.mainhand minecraft:wooden_pickaxe run item replace entity @s weapon.mainhand with minecraft:wooden_pickaxe
execute as @a[x=-138,y=60,z=164,dx=4,dy=3,dz=4] at @s if items entity @s weapon.mainhand minecraft:stone_pickaxe run item replace entity @s weapon.mainhand with minecraft:stone_pickaxe
execute as @a[x=-138,y=60,z=164,dx=4,dy=3,dz=4] at @s if items entity @s weapon.mainhand minecraft:iron_pickaxe run item replace entity @s weapon.mainhand with minecraft:iron_pickaxe
execute as @a[x=-138,y=60,z=164,dx=4,dy=3,dz=4] at @s if items entity @s weapon.mainhand minecraft:diamond_pickaxe run item replace entity @s weapon.mainhand with minecraft:diamond_pickaxe

# --- Halyard: arriving by train sets your respawn to the plaza (once) ---
execute as @a[x=0,y=90,z=90,dx=12,dy=6,dz=12,tag=!halyard_spawned] run spawnpoint @s 6 93 91
tag @a[x=0,y=90,z=90,dx=12,dy=6,dz=12,tag=!halyard_spawned] add halyard_spawned

# --- Halyard -> Oasis transit (the name_tag credential lift) ---
# Original raw blocks at (36-38,89-90,57-59): holding the $1000/500-money
# Name Tag, the lift consumes it and carries you to the Oasis; without it,
# you're told you need one. Warning is tag-throttled so it fires once per
# approach, not every 2 ticks.
execute as @a[x=35,y=88,z=57,dx=3,dy=3,dz=3] if items entity @s container.* minecraft:name_tag run tag @s add oasis_lift_go
execute as @a[tag=oasis_lift_go] run clear @s minecraft:name_tag 1
execute as @a[tag=oasis_lift_go] run tellraw @s {"text":"Credential accepted. Ascending to the Oasis.","color":"aqua"}
tp @a[tag=oasis_lift_go] 57 149 1095
tag @a[tag=oasis_lift_go] remove oasis_lift_go
execute as @a[x=35,y=88,z=57,dx=3,dy=3,dz=3,tag=!oasis_gate_warned] unless items entity @s container.* minecraft:name_tag run tellraw @s {"text":"You need a ticket! The Oasis lift takes the Name Tag credential.","color":"red"}
execute as @a[x=35,y=88,z=57,dx=3,dy=3,dz=3,tag=!oasis_gate_warned] unless items entity @s container.* minecraft:name_tag run tag @s add oasis_gate_warned
execute as @a[tag=oasis_gate_warned] unless entity @s[x=35,y=88,z=57,dx=3,dy=3,dz=3] run tag @s remove oasis_gate_warned

# --- Oasis: one-time $100 arrival grant (mod currency) ---
execute as @a[x=86,y=136,z=1023,dx=19,dy=5,dz=26,tag=!oasis_granted] run givemoney @s 100
execute as @a[x=86,y=136,z=1023,dx=19,dy=5,dz=26,tag=!oasis_granted] run tellraw @s {"text":"Welcome to the Oasis. A $100 settlement stipend has been credited to you.","color":"gold"}
tag @a[x=86,y=136,z=1023,dx=19,dy=5,dz=26,tag=!oasis_granted] add oasis_granted

schedule function basin_qol:tick 2t replace
