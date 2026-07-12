# Ensure all online players have a score (sets to 0 if uninitialized)
scoreboard players add @a rentTimer 0

# Notify players whose timer is about to hit 0 (score == 1), then decrement
execute as @a[scores={rentTimer=1}] run tellraw @s {"text":"Timer ended.","color":"red"}
scoreboard players remove @a[scores={rentTimer=1..}] rentTimer 1

# Increment lateTick each tick for overdue players (rentTimer=0, rentPaid=1)
scoreboard players add @a[scores={rentTimer=0,rentPaid=1}] lateTick 1

# Every second (20 ticks), compound the late fee by *1.1 (x11 / 10)
execute as @a[scores={lateTick=20..}] run scoreboard players operation @s lateFee *= #11 constants
execute as @a[scores={lateTick=20..}] run scoreboard players operation @s lateFee /= #10 constants
execute as @a[scores={lateTick=20..}] run scoreboard players set @s lateTick 0
execute as @a[scores={lateTick=20..}] run tellraw @s [{"text":"Late fee: ","color":"dark_red"},{"score":{"name":"@s","objective":"lateFee"}}]
