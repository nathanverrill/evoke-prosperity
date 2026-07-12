# Sets rentTimer for the executing player (1200 ticks = 1 minute — change as needed)
scoreboard players set @s rentTimer 1200
scoreboard players set @s rentPaid 1
scoreboard players set @s lateFee 100
scoreboard players set @s lateTick 0
tellraw @s {"text":"Started rentTimer.","color":"green"}
