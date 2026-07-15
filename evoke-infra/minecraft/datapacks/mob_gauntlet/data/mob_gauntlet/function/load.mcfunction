# The Mob Gauntlet -- ported from `wil_unmodded`'s basin.zip snapshot,
# a world lineage that diverged from the one actually running (see GAPS.md's
# 2026-07-15 entry). That snapshot had a real, finished 7-wave co-op arena
# ("my_mob_room" per its own structure block, "halyard arena" per a sign at
# the admin teleport hub in that snapshot) that never made it into the live
# world. The physical room (data/mob_gauntlet/structure/room.nbt) is the
# original builder's own saved structure, block-for-block, with its baked-in
# command blocks stripped out -- this pack's functions replace that logic
# cleanly rather than carrying over stale, absolute-coordinate-dependent
# Commands.
#
# Placed at the exact coordinates it occupied in the source snapshot
# (382,140,769) since nothing else occupies that space in the live world --
# avoids any coordinate translation in the logic below.
#
# NOTE: #minecraft:load only fires on a genuine server boot, not /reload
# (learned the hard way earlier this session) -- run
# "place template mob_gauntlet:room 382 140 769" once by hand after any
# /reload-based deploy.
place template mob_gauntlet:room 382 140 769

scoreboard objectives add gauntlet.active dummy
scoreboard objectives add gauntlet.wave dummy
scoreboard objectives add gauntlet.countdown dummy
scoreboard players set #global gauntlet.active 0

# Per-player ratcheted best-wave-cleared, read by evoke-minecraft-bridge the
# same way arenaBestWave already is (see check_gauntlet_progress in
# bridge.py) -- camelCase to match that existing convention, unlike this
# pack's other (dot-separated, internal-only) objectives.
scoreboard objectives add gauntletBestWave dummy
