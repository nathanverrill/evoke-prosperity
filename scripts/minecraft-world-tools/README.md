# minecraft-world-tools

Stdlib-only Python for reading real Minecraft world saves (NBT + Anvil
`.mca` region files) directly off disk — no NBT/Anvil library needed or
assumed installed. Built to investigate the actual, undocumented content of
the `true_oasis` world (see `../../MINECRAFT_WORLD_MAP.md` for what was
found); kept here because the same tools apply to any future "what's
actually built in this world" question, or to verify a change to the real
world files before deploying it.

These are read-only investigation tools. They don't modify anything and
don't need the server running — point them at a world save directory
(the folder containing `region/`), e.g.
`~/evoke-prosperity-files/minecraft/minecraft-world-files/true_oasis`.

## Tools

- **`mca_nbt_dump.py`** — the foundational NBT + Anvil parser everything
  else imports. Run directly for a quick "what entities/kiosks/villagers
  are in this one region file" pass.
- **`block_at.py`** — decodes a chunk's real block-state palette to answer
  "what block is at world X,Y,Z". This is the only way to identify plain
  terrain/architecture blocks (wool, scaffolding, stone…) — `data get
  block` over RCON only works for block *entities* (signs, chests, command
  blocks), not plain blocks.
- **`full_command_block_scan.py`** — exhaustive command-block + spawner
  inventory across an entire world, no keyword filter. Start here for "what
  mechanics exist" questions; grep the output afterward.
- **`scan_signs.py`** — exhaustive sign-text inventory, the human-readable
  half a command-block scan alone misses.
- **`scan_chunk_palettes.py`** — fast wide-area search for specific block
  *materials* (checks chunk palettes, not every coordinate) — for "is there
  scaffolding/wool/quartz anywhere in this region" questions where a
  command-block/sign search comes up empty (a pure-architecture build, like
  a parkour course, has no command-block or sign text at all).
- **`render_slice.py`** — once `scan_chunk_palettes.py` narrows down an
  area, this renders an ASCII top-down map (or a whole vertical column, or
  a "floating platform" detector) so you can actually see the shape.

## Typical workflow

1. `full_command_block_scan.py` + `scan_signs.py` for anything with real
   scripted logic or signage (most of what's documented in
   `MINECRAFT_WORLD_MAP.md` was found this way).
2. If that comes up empty in a suspected area (pure architecture, no
   scripting), `scan_chunk_palettes.py` over a wide radius for
   distinctive materials.
3. `render_slice.py --slice` / `--column` / `--floating` on the narrowed
   area to see the actual shape and confirm what it is.

## A caveat found while writing this

The world files at
`~/evoke-prosperity-files/minecraft/minecraft-world-files/` are a **static
host copy**, separate from the actual Docker-managed named volume the live
server runs on. They matched exactly everywhere checked except one block
(`-49,62,206` in `true_oasis` — `chain_command_block` in the static copy,
plain `command_block` live via RCON), so treat the static copy as reliable
but not byte-identical to the live deployment. For anything load-bearing,
cross-check against the running server over RCON.
