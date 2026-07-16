# Conveyor: delivers one of each raw material every 3 seconds (60 ticks),
# matching the source snapshot's 4 dispensers. Explicit cap on uncollected
# items sitting at the drop point (max 40) before this session's coal-block
# flood incident -- that bug was an unconditional every-tick append with no
# limit; this is deliberately timer-gated AND capped so it can never repeat
# that failure mode even if left unattended for a long time.
scoreboard players add #global cf_conveyor 1
execute if score #global cf_conveyor matches 60.. unless entity @e[type=minecraft:item,x=306,y=126,z=-134,dx=3,dy=4,dz=3,limit=40] run function crafting_factory:conveyor_drop
execute if score #global cf_conveyor matches 60.. run scoreboard players set #global cf_conveyor 0
