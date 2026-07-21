# basin_secrets: hidden content ported from true_oasis (see
# MINECRAFT_GAME_REFERENCE.md §10.3/10.5). Same self-scheduling tick
# pattern as basin_qol (tick tags don't arm on /reload).
scoreboard objectives add skelly dummy
schedule function basin_secrets:tick 2t replace
