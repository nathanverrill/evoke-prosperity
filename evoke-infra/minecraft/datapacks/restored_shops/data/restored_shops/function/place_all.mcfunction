# One-shot restore of the original build's physical shop kiosks
# (2026-07-21). The savs-common-economy mod's shops.json registers shops by
# chest coordinate, but the live world lineage (water_is_life) diverged
# before these kiosks were built -- they only exist in the true_oasis
# lineage (the world the original Will server actually ran, per its
# server.properties level-name). Each structure below is a tight
# chest+sign box exported from servers/playtest/true_oasis at the exact
# shops.json coordinates, so placement re-materializes the original
# blocks (sign text, facing, chest contents) without touching neighbors.
#
# Run manually once (function restored_shops:place_all) -- not wired to
# #minecraft:load on purpose; re-running is harmless (idempotent by
# content) but there's no reason to place on every boot.

# Keel train station: the two $100 paper ticket booths
forceload add -137 101 -137 114
place template restored_shops:ticket_booth_a -137 67 113
place template restored_shops:ticket_booth_b -137 67 101

# Keel tool store across from town hall (Benjamin's shop): pickaxe tiers + helmet
forceload add -63 200
place template restored_shops:pickaxe_shop -63 66 200

# Keel food-buying shops (rations economy)
forceload add -92 131
place template restored_shops:food_shops -92 65 131

# Halyard mob-arena drop buyers (spider eye / magma cream / slimeball)
forceload add 98 128
place template restored_shops:arena_shops 98 93 128

# Halyard crafting-factory sell shops (6 kiosks)
forceload add 320 -121 329 -114
place template restored_shops:factory_rail 327 123 -115
place template restored_shops:factory_bookshelf 328 123 -117
place template restored_shops:factory_endrod 323 123 -115
place template restored_shops:factory_piston 320 123 -116
place template restored_shops:factory_beacon 328 123 -121
place template restored_shops:factory_cake 320 123 -120

# Halyard: the $1000 Name Tag shop (the ticket toward Oasis)
forceload add 32 56
place template restored_shops:oasis_ticket 32 93 56

forceload remove -137 101 -137 114
forceload remove -63 200
forceload remove -92 131
forceload remove 98 128
forceload remove 320 -121 329 -114
forceload remove 32 56

say Restored shop kiosks placed.
