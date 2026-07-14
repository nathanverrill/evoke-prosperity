# Triggered by the button at the machine via the original first command
# block, now: "execute as @p at @s run function coinflip:play". Running the
# whole payment/flip/payout sequence as the SAME resolved @s throughout
# (rather than each step separately re-picking the nearest player via @p,
# as the original 6 raw command blocks did) removes any chance of the
# "nearest player" target drifting mid-sequence if a second player is
# standing nearby.
execute store result score @s hasgold run clear @s minecraft:gold_ingot 0
execute if score @s hasgold matches 2.. run clear @s minecraft:gold_ingot 2
execute store result score @s coinflip run random value 0..1

# Payout and "you won" both re-check hasgold (captured fresh above, before
# payment) rather than trusting the flip alone -- this is the fix for the
# free-gold bug: a player with <2 gold used to still get a 50% shot at a
# real payout because the flip and payout ran unconditionally.
execute if score @s coinflip matches 1 if score @s hasgold matches 2.. run give @s minecraft:gold_ingot 3
execute if score @s coinflip matches 1 if score @s hasgold matches 2.. run tellraw @s {"text":"You won!","color":"gold"}
execute if score @s coinflip matches 0 run tellraw @s {"text":"You lost! Better luck next time.","color":"red","bold":true}
