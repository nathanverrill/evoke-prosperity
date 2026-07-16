# Cohort-wide Adventure-mode lock, admin-triggered by Mission 2's release
# (see evoke-minecraft-bridge/bridge.py's handle_mission_released). Design
# intent: free-roam exploration the first couple of days ("awe and
# wonder"), then locked out of building/breaking once Mission 2 releases,
# so players engage with the minigames instead of the open world.
#
# This replaces an earlier, broken attempt at the same idea (raw command
# blocks in the mines rooms, see MINECRAFT_WORLD_MAP.md section 3): 3 of 4
# `gamemode adventure @s` commands there had no `execute as` wrapper so
# they silently no-op'd, and the one that did work had no restore-to-
# survival path anywhere in the world, permanently stranding whoever
# triggered it. This mechanism is deliberately one-directional by design
# (the lock is meant to persist, not a bug to route around) but is a
# world-scoped flag, not a per-player point of no return -- flipping
# #global missions_locked back to 0 releases everyone currently caught by
# it, unlike the original.
scoreboard objectives add missions_locked dummy
scoreboard players add #global missions_locked 0
