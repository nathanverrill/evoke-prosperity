# Halyard Crafting Factory -- ported from the cu-internship design docs
# (halyard-minigames.txt) and the physical assets found in the wil_unmodded
# snapshot (never made it into the live world lineage, same situation as
# the Mob Gauntlet). Two pieces ported with confidence tonight: the raw-
# material conveyor and the three ingredient-trading villagers. The sell
# shops ("$4[Admin Shop]" signs in the source snapshot) are NOT ported --
# traced their mechanism and found no command-block logic behind them at
# all, meaning they were tied to Savs-Common-Economy, a mod dependency that
# was never actually fetched (confirmed empty on disk earlier this
# session). Rather than guess at a shop mechanism that may never have
# worked, that piece is deliberately left for a follow-up pass with a
# proven pattern (matching the mines' working coal-shop command blocks)
# instead of shipping something untested overnight.
scoreboard objectives add cf_conveyor dummy
# xpLevel mirrors the player's real XP level (vanilla read-only 'level'
# criterion) -- the factory's time-currency, ported from true_oasis
# (see MINECRAFT_GAME_REFERENCE.md §10.1 and xp_time.mcfunction).
scoreboard objectives add xpLevel level

# Villagers are tagged so a restart never re-summons duplicates.
execute unless entity @e[type=villager,tag=cf_overworld_villager] run summon villager 306 128 -134 {Tags:["cf_overworld_villager"],CustomName:"Overworld Villager",CustomNameVisible:1b,PersistenceRequired:1b,VillagerData:{profession:"minecraft:farmer",level:2,type:"minecraft:plains"},Offers:{Recipes:[{buy:{id:"minecraft:emerald",count:6},sell:{id:"minecraft:rabbit_hide",count:1},rewardExp:0b,maxUses:999999,xp:0},{buy:{id:"minecraft:emerald",count:3},sell:{id:"minecraft:slime_ball",count:1},rewardExp:0b,maxUses:999999,xp:0}]}}

execute unless entity @e[type=villager,tag=cf_nether_villager] run summon villager 304 128 -134 {Tags:["cf_nether_villager"],CustomName:"Nether Villager",CustomNameVisible:1b,PersistenceRequired:1b,VillagerData:{profession:"minecraft:mason",level:2,type:"minecraft:plains"},Offers:{Recipes:[{buy:{id:"minecraft:emerald",count:5},sell:{id:"minecraft:blaze_rod",count:1},rewardExp:0b,maxUses:999999,xp:0},{buy:{id:"minecraft:emerald",count:10},sell:{id:"minecraft:nether_star",count:1},rewardExp:0b,maxUses:999999,xp:0}]}}

execute unless entity @e[type=villager,tag=cf_ender_villager] run summon villager 308 128 -134 {Tags:["cf_ender_villager"],CustomName:"Ender Villager",CustomNameVisible:1b,PersistenceRequired:1b,VillagerData:{profession:"minecraft:butcher",level:2,type:"minecraft:plains"},Offers:{Recipes:[{buy:{id:"minecraft:emerald",count:4},sell:{id:"minecraft:ender_pearl",count:1},rewardExp:0b,maxUses:999999,xp:0},{buy:{id:"minecraft:emerald",count:4},buyB:{id:"minecraft:cobblestone",count:1},sell:{id:"minecraft:chorus_fruit",count:1},rewardExp:0b,maxUses:999999,xp:0}]}}
