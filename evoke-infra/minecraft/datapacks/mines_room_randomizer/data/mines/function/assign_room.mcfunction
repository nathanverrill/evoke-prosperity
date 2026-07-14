# Consolidated from 2 duplicate 13-block clusters -- both did the exact
# same thing, watching a global `mine_tp` tag instead of being called
# directly, so a tag added by either entrance was liable to be processed
# by both clusters (double-teleport risk, harmless but redundant). Called
# directly now -- "execute as @p at @s run function mines:assign_room" --
# from each of the 2 real entrance triggers (still physical
# buttons/plates in the world; only their Command changed).
#
# Deliberately dropped in this extraction:
# - a bare `say assigning_room` that broadcast to the WHOLE server on
#   every single use of the mines, for every player online. Replaced with
#   a private message to the entering player only.
# - 4 `gamemode adventure @s` commands. 3 of the 4 (rooms 01/10/11) were
#   bare with no `execute as` wrapper, so @s had no entity context and
#   they always failed ("No player was found" -- verified live via RCON).
#   The 4th (room00) DID have a working wrapper, but nothing anywhere in
#   the entire world ever sets gamemode back to survival -- so the one
#   working copy of this would have permanently stranded whoever
#   triggered it in adventure mode, unable to break blocks, including the
#   coal they're there to mine. Left out for all 4 rooms rather than
#   "completed" for the other 3, since completing it would turn a mostly
#   dead-code no-op into a real trap.
tellraw @s {"text":"Assigning your room...","color":"gray","italic":true}
execute if score room00 room matches 1 run tp @s -132 40 -83
execute if score room10 room matches 1 run tp @s -132 40 -113
execute if score room01 room matches 1 run tp @s -104 40 -82
execute if score room11 room matches 1 run tp @s -105 40 -113
