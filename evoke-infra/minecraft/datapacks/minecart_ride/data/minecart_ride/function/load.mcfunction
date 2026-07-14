# Minecart/dropper ride -- extracted from 9 raw command blocks physically
# placed across 3 parallel lanes at ~(304-306, 128-134, -142 to -144), see
# MINECRAFT_WORLD_MAP.md section 3. All 3 lanes originally read/wrote the
# same `rail1 cartTimer` holder, so the shared counter advanced up to 3x
# too fast (GAPS.md's 2026-07-14 robustness-pass row); rail2/rail3 already
# exist on the live world from that fix, declared here too for portability.
scoreboard objectives add cartTimer dummy
