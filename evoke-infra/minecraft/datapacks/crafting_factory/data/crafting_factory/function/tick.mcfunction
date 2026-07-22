# Conveyor: delivers one of each raw material every 3 seconds (60 ticks),
# matching the source snapshot's 4 dispensers. Explicit cap on uncollected
# items sitting at the drop point (max 40) before this session's coal-block
# flood incident -- that bug was an unconditional every-tick append with no
# limit; this is deliberately timer-gated AND capped so it can never repeat
# that failure mode even if left unattended for a long time.
# 2026-07-22 incident fix: the old guard's box (x=306..309, z=-134..-131)
# missed the actual drop point (306.89, 127, -134.04) by 0.04 blocks on z,
# so the cap never engaged and ~86k items accumulated, freezing a tick for
# 60s (watchdog crash). It also used `unless entity` + limit=40, which
# actually stops at the FIRST match, not the 40th. Now: count items in a
# box that genuinely contains the drop point, and only drop below 40.
scoreboard players add #global cf_conveyor 1
execute if score #global cf_conveyor matches 60.. store result score #cnt cf_conveyor if entity @e[type=minecraft:item,x=304,y=125,z=-137,dx=6,dy=6,dz=6]
execute if score #global cf_conveyor matches 60.. if score #cnt cf_conveyor matches ..39 run function crafting_factory:conveyor_drop
execute if score #global cf_conveyor matches 60.. run scoreboard players set #global cf_conveyor 0

# XP-time economy (true_oasis port): XP levels are the time you can afford
# inside the factory. Halyard town grants +1 level per 5s (cap 60); the
# factory floor drains 1 per 5s; at 0 you're ejected to the plaza. The
# entry pad at (2,92,98) requires level 60+ (its command block was patched
# live to the original gated version 2026-07-21).
scoreboard players add #xt cf_conveyor 1
execute if score #xt cf_conveyor matches 100.. run function crafting_factory:xp_time
execute if score #xt cf_conveyor matches 100.. run scoreboard players set #xt cf_conveyor 0
