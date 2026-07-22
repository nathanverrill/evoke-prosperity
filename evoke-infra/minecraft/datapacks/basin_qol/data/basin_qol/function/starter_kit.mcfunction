# Starter-kit post by the villager pen. The button's impulse command block
# at (-45,64,191) calls this; the original impulse->chain wiring (summon /
# fill-from-chest / kill) never fired its chain blocks in this world copy,
# so pressing the button popped an empty, immortal cart (found 2026-07-22).
# One function now does the whole press: clear any previous cart, pop a
# fresh one on the post, stock it from the hidden supply chest.
kill @e[type=chest_minecart,tag=lootCart,x=-48,y=60,z=187,dx=9,dy=9,dz=9]
summon minecraft:chest_minecart -43.5 66.0 191.5 {Tags:["lootCart"]}
data modify entity @e[type=chest_minecart,tag=lootCart,limit=1] Items set from block -44 62 192 Items
