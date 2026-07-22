# spawn_intro: the mountaintop arrival beat. World spawn is set to the
# summit plateau north of keel town (-34 197 -32, set via setworldspawn +
# gamerule spawnRadius 0, both stored in level.dat, not here). This pack
# adds the one-shot placement + "look around, then descend" prompt, which
# also catches pre-existing/reset players who would otherwise log back in
# wherever they last stood.
# Same self-scheduling tick pattern as basin_qol/basin_secrets (tick tags
# don't arm on /reload on this server).
schedule function spawn_intro:tick 2t replace
