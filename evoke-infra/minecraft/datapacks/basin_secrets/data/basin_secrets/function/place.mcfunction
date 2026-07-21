# One-shot placement of the two hidden builds (run manually once per
# world; re-running just re-places identical blocks). Structures were
# exported from servers/playtest/true_oasis with command blocks stripped;
# logic lives in tick.mcfunction instead.

# Craig's maintenance tunnel under the town hall stairs -- carved out of
# solid andesite in the live world (the tunnel never existed in this
# lineage). His NPC persona hints at it "if you're tight on cash."
forceload add -14 188 -5 199
place template basin_secrets:town_hall_tunnel -14 56 188

# The mountain shrine (quartz + water-glass) between Halyard and the
# summit, plus a bone-block pedestal at its center: the original ritual
# was global (any diamond dropped on any bone block), but the live world
# had no bone block anywhere -- this gives the easter egg a home.
forceload add 35 497 43 505
place template basin_secrets:ritual_shrine 35 142 497
setblock 39 146 501 minecraft:bone_block

forceload remove -14 188 -5 199
forceload remove 35 497 43 505
say Basin secrets placed.
