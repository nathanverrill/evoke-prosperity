# Runs every 2 ticks (self-scheduling; armed by basin_secrets:load).

# --- The diamond lightning ritual (global, as in the original) ---
# A dropped diamond resting on a bone block charges up (crit particles +
# fire-extinguish hiss), then takes a lightning strike. Pure spectacle --
# no reward attached, same as the original.
# No nbt= selectors here: an nbt= match serializes the FULL NBT of every
# candidate entity per command, and five of those every 2 ticks froze a
# tick for 60s and watchdog-crashed the live server (2026-07-22) when
# item entities piled up. The block check runs first (cheap), and `if
# items ... contents` compares one stack without serializing anything;
# the follow-up lines select on the skelly score, which only diamonds
# ever receive.
execute as @e[type=item] at @s if block ~ ~-1 ~ minecraft:bone_block if items entity @s contents minecraft:diamond run scoreboard players add @s skelly 1
execute as @e[type=item,scores={skelly=1..10}] at @s run particle minecraft:crit ~ ~ ~ 0.2 0.2 0.2 0.1 10
execute as @e[type=item,scores={skelly=1..10}] at @s run playsound minecraft:block.fire.extinguish block @a[distance=..16]
execute as @e[type=item,scores={skelly=11..},tag=!struck] at @s run summon minecraft:lightning_bolt ~ ~ ~
execute as @e[type=item,scores={skelly=11..},tag=!struck] run tag @s add struck

# --- Craig's balance-reset terminal (tunnel under the town hall) ---
# Standing at the terminal wipes your mod-economy balance back to the $10
# default (the original command block ran `resetmoney @p`). Tag-gated so
# it fires once per visit; the tag clears when you leave the tunnel.
execute as @a[x=-9,y=58,z=193,dx=1,dy=2,dz=2,tag=!panel_used] run tellraw @s {"text":"The old Alpha terminal hums...","color":"dark_red"}
execute as @a[x=-9,y=58,z=193,dx=1,dy=2,dz=2,tag=!panel_used] run scoreboard players set @s balanceWipe 1
tag @a[x=-9,y=58,z=193,dx=1,dy=2,dz=2,tag=!panel_used] add panel_used
execute as @a[tag=panel_used] unless entity @s[x=-14,y=56,z=188,dx=9,dy=7,dz=11] run tag @s remove panel_used

schedule function basin_secrets:tick 2t replace
