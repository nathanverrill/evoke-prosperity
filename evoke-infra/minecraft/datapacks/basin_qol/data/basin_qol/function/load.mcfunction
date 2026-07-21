# basin_qol: quality-of-life systems ported from the true_oasis lineage
# (the original server's world -- see MINECRAFT_GAME_REFERENCE.md §10.6-7).
#
# The tick loop is self-scheduling (schedule ... replace) instead of a
# #minecraft:tick tag: tick/load tags only arm on a real server boot, not
# on /reload, so a tag-based loop can't be brought live on the running
# Apex server without a restart. This #minecraft:load tag arms the loop at
# every future boot, and `schedule ... replace` guarantees exactly one
# scheduled instance no matter how many times load runs.
schedule function basin_qol:tick 2t replace
