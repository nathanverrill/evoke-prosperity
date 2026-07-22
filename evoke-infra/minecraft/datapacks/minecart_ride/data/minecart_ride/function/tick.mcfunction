# Player-gated (2026-07-22): the lanes only run while someone is within
# ~20 blocks of the ride (center ~305,131,-143), so nothing spawns into an
# empty world. The per-lane cart cap stays as a second guard; see
# lane1.mcfunction's incident note.
execute if entity @a[x=285,y=111,z=-163,dx=40,dy=40,dz=40] run function minecart_ride:lane1
execute if entity @a[x=285,y=111,z=-163,dx=40,dy=40,dz=40] run function minecart_ride:lane2
execute if entity @a[x=285,y=111,z=-163,dx=40,dy=40,dz=40] run function minecart_ride:lane3
