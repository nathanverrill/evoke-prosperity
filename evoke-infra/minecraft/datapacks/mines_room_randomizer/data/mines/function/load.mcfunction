# Mines room-randomizer -- extracted from 2 duplicate 13-block command
# block clusters (~(-196 to -193, 40-43, -119) and ~(-140 to -136, 56-59,
# 159)) plus 8 occupancy-detection blocks (~(-128/-100, 27-30, -80/-113)),
# all raw command blocks with no prior source file. See
# MINECRAFT_WORLD_MAP.md section 3 and GAPS.md's 2026-07-14/15
# robustness-pass rows. `room` already exists on the live world; declared
# here too for portability.
scoreboard objectives add room dummy
