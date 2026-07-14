"""Fast wide-area search for specific block materials, by chunk palette
rather than by walking every coordinate. A chunk section's block palette is
a short list (usually <50 entries) of every distinct block type physically
present in that 16x16x16 cube -- checking membership in that list is orders
of magnitude cheaper than calling block_at.py's get_block() once per
coordinate across a big volume, since it only requires decoding each
chunk's NBT once, not per-block bit-unpacking.

This is how the hidden parkour shaft in MINECRAFT_WORLD_MAP.md §7 was
actually found: full_command_block_scan.py and scan_signs.py came up empty
around the suspected area (a pure-architecture course has no command-block
or sign text to grep for), so this scanned a wide radius for scaffolding/
wool/glass -- materials chosen for visual jump-target contrast, not
structural building -- and found a dense, localized cluster that
render_slice.py then confirmed was a real climbing shaft.

Usage:
    python3 scan_chunk_palettes.py /path/to/world x0 x1 z0 z1 [material,material,...]

    # defaults to a broad parkour/decorative-material list if none given
    python3 scan_chunk_palettes.py /path/to/world -200 150 50 320
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from block_at import _read_chunk_nbt

DEFAULT_MATERIALS = [
    'wool', 'concrete', 'quartz', 'slime_block', 'honey_block', 'prismarine',
    'purpur', 'stained_glass', 'nether_brick', 'end_rod', 'sea_lantern',
    'magma_block', 'scaffolding',
]


def interesting(name, substrings):
    return any(s in name for s in substrings)


if __name__ == '__main__':
    world_dir = sys.argv[1]
    x0, x1, z0, z1 = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
    substrings = sys.argv[6].split(',') if len(sys.argv) > 6 else DEFAULT_MATERIALS

    cx0, cx1 = x0 >> 4, x1 >> 4
    cz0, cz1 = z0 >> 4, z1 >> 4

    hits = {}
    checked = 0
    for cx in range(cx0, cx1 + 1):
        for cz in range(cz0, cz1 + 1):
            region_x, region_z = cx >> 5, cz >> 5
            local_cx, local_cz = cx % 32, cz % 32
            idx = local_cx + local_cz * 32
            region_path = os.path.join(world_dir, 'region', f'r.{region_x}.{region_z}.mca')
            if not os.path.exists(region_path):
                continue
            chunk = _read_chunk_nbt(region_path, idx)
            checked += 1
            if chunk is None:
                continue
            sections = chunk.get('sections') or []
            for s in sections:
                bs = s.get('block_states')
                if not bs:
                    continue
                palette = bs.get('palette') or []
                for entry in palette:
                    name = entry.get('Name', '')
                    if interesting(name, substrings):
                        hits.setdefault(name, set()).add((cx * 16, s.get('Y', 0) * 16, cz * 16))

    print(f"Checked {checked} chunks", file=sys.stderr)
    for name, chunk_origins in sorted(hits.items(), key=lambda kv: -len(kv[1])):
        print(f"{len(chunk_origins):4d} chunk-sections  {name}")
        for o in list(chunk_origins)[:8]:
            print(f"      near {o}")
