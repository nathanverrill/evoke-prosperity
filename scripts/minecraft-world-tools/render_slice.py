"""Renders an ASCII top-down slice of a world save at a fixed Y level, and
optionally lists "floating" blocks (solid, air below, mostly air on the
sides) across a Y range -- the pattern that actually revealed the shape of
the hidden parkour shaft in MINECRAFT_WORLD_MAP.md §7. scan_chunk_palettes.py
finds *that* a material exists somewhere in a wide area; this tool answers
"what does it actually look like" once you have a smaller area to look at.

Usage:
    # one flat map at a single Y
    python3 render_slice.py /path/to/world --slice X0 X1 Z0 Z1 Y

    # a full vertical scan, printing every Y level that has any content
    python3 render_slice.py /path/to/world --column X0 X1 Z0 Z1 Y0 Y1

    # floating/platform-like blocks across a Y range (air below + mostly
    # air on the sides -- distinguishes jump platforms from solid walls)
    python3 render_slice.py /path/to/world --floating X0 X1 Z0 Z1 Y0 Y1
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from block_at import get_block

AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
TERRAIN = AIR | {
    "minecraft:stone", "minecraft:deepslate", "minecraft:dirt",
    "minecraft:coarse_dirt", "minecraft:grass_block", "minecraft:water",
    "minecraft:gravel", "minecraft:andesite", "minecraft:diorite",
    "minecraft:granite", "minecraft:tuff", "minecraft:calcite",
}


def sym(name):
    if name is None or name in AIR:
        return '.'
    if name.startswith("BAD_INDEX") or name == "NO_SECTIONS":
        return '?'
    if 'scaffold' in name:
        return 'S'
    if 'wool' in name or 'concrete' in name:
        return 'W'
    if 'glass' in name:
        return 'G'
    if 'chest' in name:
        return 'C'
    if 'sign' in name:
        return 'N'
    return '#'


def print_slice(world_dir, x0, x1, z0, z1, y):
    print(f"--- y={y} (x {x0}..{x1} across, z {z0}..{z1} down) ---")
    for z in range(z0, z1):
        row = ''.join(sym(get_block(world_dir, x, y, z)) for x in range(x0, x1))
        print(f"{z:5d} {row}")


def print_column(world_dir, x0, x1, z0, z1, y0, y1):
    for y in range(y0, y1):
        rows = []
        any_content = False
        for z in range(z0, z1):
            row = ''.join(sym(get_block(world_dir, x, y, z)) for x in range(x0, x1))
            if row.count('.') < len(row):
                any_content = True
            rows.append((z, row))
        if any_content:
            print(f"--- y={y} ---")
            for z, row in rows:
                print(f"{z:5d} {row}")


def find_floating(world_dir, x0, x1, z0, z1, y0, y1):
    """Blocks with air directly below and at least 2 of their 4 horizontal
    neighbors also air -- catches jump platforms/scaffolding segments while
    mostly skipping solid walls and floors."""
    cache = {}

    def b(x, y, z):
        key = (x, y, z)
        if key not in cache:
            cache[key] = get_block(world_dir, x, y, z)
        return cache[key]

    floating = []
    for y in range(y0, y1):
        for x in range(x0, x1):
            for z in range(z0, z1):
                here = b(x, y, z)
                if here in AIR or here is None or here.startswith("BAD_INDEX") or here == "NO_SECTIONS":
                    continue
                below = b(x, y - 1, z)
                n_air = sum(1 for dx, dz in [(1, 0), (-1, 0), (0, 1), (0, -1)] if b(x + dx, y, z + dz) in AIR)
                if below in AIR and n_air >= 2:
                    floating.append((x, y, z, here))
    return floating


if __name__ == '__main__':
    world_dir = sys.argv[1]
    mode = sys.argv[2]
    args = [int(a) for a in sys.argv[3:]]

    if mode == '--slice':
        x0, x1, z0, z1, y = args
        print_slice(world_dir, x0, x1, z0, z1, y)
    elif mode == '--column':
        x0, x1, z0, z1, y0, y1 = args
        print_column(world_dir, x0, x1, z0, z1, y0, y1)
    elif mode == '--floating':
        x0, x1, z0, z1, y0, y1 = args
        hits = find_floating(world_dir, x0, x1, z0, z1, y0, y1)
        print(f"{len(hits)} floating/platform-like blocks in y={y0}..{y1}")
        for x, y, z, name in sorted(hits, key=lambda t: (t[1], t[0], t[2])):
            print(f"  {x},{y},{z}: {name}")
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
