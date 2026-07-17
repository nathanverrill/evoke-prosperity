# Always-Adventure baseline, unconditional regardless of phase -- the
# "never destroy the environment, ever" rule. Only catches players
# actually in Survival, so an admin who's deliberately set themselves to
# Creative (for building/testing) isn't fought every tick -- matches the
# original gamemode_lock's same "only correct survival" scope, just
# unconditional instead of flag-gated.
execute as @a[gamemode=survival] run gamemode adventure @s

# Vision phase: everyone flies. Lived phase: nobody does (and if you were
# mid-air flying when it toggled off, stop immediately rather than
# falling with flight still nominally on).
execute if score #global vision_phase matches 1 as @a run data merge entity @s {abilities:{mayfly:1b}}
execute if score #global vision_phase matches 0 as @a run data merge entity @s {abilities:{mayfly:0b,flying:0b}}
