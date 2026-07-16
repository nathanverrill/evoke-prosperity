# Runs every tick, not just on join: catches new joiners (who always start
# in Survival per server.properties) within one tick, and re-catches anyone
# an admin manually sets back to Survival while locked. Cheap when unlocked
# -- the whole check short-circuits on the scoreboard match failing.
execute if score #global missions_locked matches 1 as @a[gamemode=survival] run gamemode adventure @s
