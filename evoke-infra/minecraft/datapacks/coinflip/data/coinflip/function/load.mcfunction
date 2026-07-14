# Coinflip gambling -- extracted from 6 raw command blocks physically
# placed at ~(-137 to -142, 62, 149), see MINECRAFT_WORLD_MAP.md section 3
# and GAPS.md's 2026-07-14 robustness-pass row (the free-gold bug this
# fixed: payout used to fire even when the player hadn't actually paid).
# These objectives already exist on the live world from the original
# raw-command-block version; declared here too so this pack is portable.
scoreboard objectives add hasgold dummy
scoreboard objectives add coinflip dummy
