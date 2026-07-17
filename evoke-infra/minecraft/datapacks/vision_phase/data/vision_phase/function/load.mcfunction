# Replaces the earlier gamemode_lock datapack, which was built on the
# wrong premise (a Survival<->Adventure toggle -- Survival allows
# destruction, which conflicts with "no one is ever supposed to be able
# to destroy the environment"). Adventure is now the permanent, universal
# baseline (see tick.mcfunction) -- the only thing this actually toggles
# is flight (the "vision" -- flying freely over the whole world before
# anything constrains you) and, separately, the multi-NPC billbot mod
# reads this same scoreboard value to decide whether NPCs respond at all
# ("nobody can see or hear you yet" during the vision).
#
# Mining still works in Adventure mode unchanged -- mines_lift_precheck
# already tags the issued pickaxe with a can_break component scoped to
# exactly stone/cobblestone/coal_ore/coal_block, the vanilla mechanic for
# curated destruction in adventure maps. Nothing about this datapack
# touches or needs to touch that.
scoreboard objectives add vision_phase dummy

# Starts in the vision phase (1) on a genuinely fresh world -- but only
# if the objective has never held a value at all, so a restart never
# resets an admin's in-progress toggle back to 1.
execute unless score #global vision_phase matches -2147483648..2147483647 run scoreboard players set #global vision_phase 1
