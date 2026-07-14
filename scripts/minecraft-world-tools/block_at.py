"""Answers "what block is at this exact world coordinate" by decoding a
chunk's real block-state palette + bit-packed section data -- not just
block *entities* (signs/chests/command blocks), which is all `data get
block` can see over RCON. This is how the hidden parkour shaft in
MINECRAFT_WORLD_MAP.md §7 was actually mapped: plain terrain/scaffolding/
wool blocks have no NBT of their own, so there's no RCON shortcut for them.

Verified against known ground truth before trusting it: the command block
at (-49, 63, 206) in true_oasis (the real B1llbot kiosk, MINECRAFT_WORLD_MAP.md
§2) round-trips correctly, matching what RCON's `data get block` independently
confirmed.

Usage:
    from block_at import get_block
    get_block(world_dir, x, y, z)  # -> "minecraft:stone", "minecraft:air", ...

    python3 block_at.py /path/to/world x y z
"""
import sys, os, math, struct, zlib, gzip

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mca_nbt_dump import parse_nbt

_region_cache = {}


def _read_chunk_nbt(region_path, idx):
    if not os.path.exists(region_path):
        return None
    with open(region_path, 'rb') as f:
        header = f.read(8192)
        if len(header) < 8192:
            return None
        off_entry = header[idx * 4:idx * 4 + 4]
        offset = (off_entry[0] << 16) | (off_entry[1] << 8) | off_entry[2]
        if offset == 0:
            return None
        f.seek(offset * 4096)
        length_bytes = f.read(4)
        if len(length_bytes) < 4:
            return None
        length = struct.unpack('>I', length_bytes)[0]
        comp_type = f.read(1)[0]
        chunk_data = f.read(length - 1)
    if comp_type == 2:
        raw = zlib.decompress(chunk_data)
    elif comp_type == 1:
        raw = gzip.decompress(chunk_data)
    elif comp_type == 3:
        raw = chunk_data
    else:
        return None
    _name, nbt = parse_nbt(raw)
    return nbt


def get_block(world_dir, x, y, z):
    """world_dir is a world save root (the folder containing `region/`),
    e.g. .../minecraft-world-files/true_oasis. Results are cached per
    chunk -- cheap to call repeatedly across a scan of the same area."""
    chunk_x, chunk_z = x >> 4, z >> 4
    region_x, region_z = chunk_x >> 5, chunk_z >> 5
    local_cx, local_cz = chunk_x % 32, chunk_z % 32
    idx = local_cx + local_cz * 32
    region_path = os.path.join(world_dir, 'region', f'r.{region_x}.{region_z}.mca')

    cache_key = (region_path, idx)
    if cache_key not in _region_cache:
        _region_cache[cache_key] = _read_chunk_nbt(region_path, idx)
    chunk = _region_cache[cache_key]
    if chunk is None:
        return None

    sections = chunk.get('sections')
    if sections is None:
        return "NO_SECTIONS"
    section_y = y >> 4
    section = next((s for s in sections if s.get('Y') == section_y), None)
    if section is None:
        return "minecraft:air"  # unloaded/empty section -> air

    bs = section.get('block_states')
    if bs is None:
        return "minecraft:air"
    palette = bs.get('palette')
    if not palette:
        return "minecraft:air"
    if len(palette) == 1:
        return palette[0].get('Name', '?')

    data = bs.get('data')
    if data is None:
        return palette[0].get('Name', '?')

    bits = max(4, math.ceil(math.log2(len(palette))))
    blocks_per_long = 64 // bits
    lx, ly, lz = x & 15, y & 15, z & 15
    block_index = (ly * 16 + lz) * 16 + lx
    long_index = block_index // blocks_per_long
    bit_offset = (block_index % blocks_per_long) * bits
    raw_long = data[long_index] & 0xFFFFFFFFFFFFFFFF
    palette_index = (raw_long >> bit_offset) & ((1 << bits) - 1)
    if palette_index >= len(palette):
        return f"BAD_INDEX({palette_index}/{len(palette)})"
    return palette[palette_index].get('Name', '?')


if __name__ == '__main__':
    world_dir = sys.argv[1]
    x, y, z = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    print(get_block(world_dir, x, y, z))
