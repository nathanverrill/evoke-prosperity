# Same drop point and materials as the source snapshot's 4 command blocks
# (red_sand, obsidian, oak_log, cobblestone), just consolidated into one
# timer-gated call instead of 4 unconditional always-active blocks.
summon minecraft:item 306.89 127.00 -134.04 {Item:{id:"minecraft:red_sand",count:1}}
summon minecraft:item 306.89 127.00 -134.04 {Item:{id:"minecraft:obsidian",count:1}}
summon minecraft:item 306.89 127.00 -134.04 {Item:{id:"minecraft:oak_log",count:1}}
summon minecraft:item 306.89 127.00 -134.04 {Item:{id:"minecraft:cobblestone",count:1}}
# Emeralds arrive on the belt too, but not every cycle (true_oasis had an
# rng-gated emerald dropper; MINECRAFT_MINIGAMES.md: "items are not
# guaranteed") -- roughly one emerald per 3 cycles, the currency for the
# three ingredient villagers' trades.
execute store result score #roll cf_conveyor run random value 1..3
execute if score #roll cf_conveyor matches 1 run summon minecraft:item 306.89 127.00 -134.04 {Item:{id:"minecraft:emerald",count:1}}
