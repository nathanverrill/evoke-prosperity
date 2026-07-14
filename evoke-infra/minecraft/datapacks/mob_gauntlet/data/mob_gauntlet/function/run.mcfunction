# Called every tick while a run is active.

# Safety abort: the original had this exact idea (an unconditional kill
# right after an "execute unless entity @a[distance=..50]" with no run
# clause -- two physically separate command blocks, so the condition never
# actually gated anything and always-fired every trigger). Fixed here as
# one real command, and centered on the actual room rather than the
# original's control-corridor position ~40 blocks away.
execute unless entity @a[x=393,y=145,z=788,distance=..50] run function mob_gauntlet:abort

# Wave-clear check: only once actually active, not already mid-countdown,
# and no mob.wave entities left standing.
execute if score #global gauntlet.countdown matches 0 unless entity @e[tag=mob.wave] run scoreboard players set #global gauntlet.countdown 1

execute if score #global gauntlet.countdown matches 1.. run function mob_gauntlet:countdown_tick
