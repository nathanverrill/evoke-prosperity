# Create the rentTimer scoreboard objective (dummy = not tied to any game event)
scoreboard objectives add rentTimer dummy
scoreboard objectives add rentPaid dummy
scoreboard objectives add lateFee dummy
scoreboard objectives add lateTick dummy

# Constants for *1.1 approximation (multiply by 11, divide by 10)
scoreboard objectives add constants dummy
scoreboard players set #11 constants 11
scoreboard players set #10 constants 10
