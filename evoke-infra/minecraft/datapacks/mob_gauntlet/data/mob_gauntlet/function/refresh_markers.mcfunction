# Re-randomizes the 30 spawn-point candidates each wave draws from -- the
# original summoned exactly 30 markers then spread them with a single
# spreadplayers call; refreshed once per wave here rather than replicating
# the original's ambiguous (possibly per-tick) refresh timing.
kill @e[tag=marker.spawn]
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
summon marker 394 140 798 {Tags:["marker.spawn"]}
spreadplayers 394 798 1 10 under 143 false @e[tag=marker.spawn]
