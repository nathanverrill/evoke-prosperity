"""Exports a bounding box of a real world save as a vanilla structure NBT
file (.nbt), the same format `/place template` reads. Companion to
block_at.py (read-only) -- this is the write side, built specifically to
pull the pre-existing 7-wave mob arena out of the `wil_unmodded` basin
snapshot (see GAPS.md / MINECRAFT_WORLD_MAP.md) into a portable datapack,
since that arena's physical structure never made it into the world lineage
actually running today.

Command blocks are deliberately excluded (written out as air) -- the
datapack's own .mcfunction logic replaces them; baking stale,
coordinate-dependent Command NBT into a relocatable structure file would
defeat the point of extracting it.

Usage:
    python3 export_structure.py /path/to/world x0 y0 z0 x1 y1 z1 out.nbt
"""
import sys, os, struct, gzip, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mca_nbt_dump import parse_nbt
from block_at import _read_chunk_nbt

COMMAND_BLOCK_IDS = {
    "minecraft:command_block", "minecraft:chain_command_block",
    "minecraft:repeating_command_block",
}

_region_cache = {}


def _chunk_at(world_dir, x, z):
    chunk_x, chunk_z = x >> 4, z >> 4
    region_x, region_z = chunk_x >> 5, chunk_z >> 5
    local_cx, local_cz = chunk_x % 32, chunk_z % 32
    idx = local_cx + local_cz * 32
    region_path = os.path.join(world_dir, 'region', f'r.{region_x}.{region_z}.mca')
    key = (region_path, idx)
    if key not in _region_cache:
        _region_cache[key] = _read_chunk_nbt(region_path, idx)
    return _region_cache[key]


def _block_entity_at(chunk, x, y, z):
    for be in chunk.get('block_entities') or []:
        if be.get('x') == x and be.get('y') == y and be.get('z') == z:
            return be
    return None


def get_block_full(world_dir, x, y, z):
    """Returns (palette_entry_dict, block_entity_nbt_or_None)."""
    chunk = _chunk_at(world_dir, x, z)
    if chunk is None:
        return {"Name": "minecraft:air"}, None
    sections = chunk.get('sections')
    if not sections:
        return {"Name": "minecraft:air"}, None
    section_y = y >> 4
    section = next((s for s in sections if s.get('Y') == section_y), None)
    if section is None:
        return {"Name": "minecraft:air"}, None
    bs = section.get('block_states')
    if bs is None:
        return {"Name": "minecraft:air"}, None
    palette = bs.get('palette')
    if not palette:
        return {"Name": "minecraft:air"}, None

    if len(palette) == 1:
        entry = palette[0]
    else:
        data = bs.get('data')
        if data is None:
            entry = palette[0]
        else:
            bits = max(4, math.ceil(math.log2(len(palette))))
            blocks_per_long = 64 // bits
            lx, ly, lz = x & 15, y & 15, z & 15
            block_index = (ly * 16 + lz) * 16 + lx
            long_index = block_index // blocks_per_long
            bit_offset = (block_index % blocks_per_long) * bits
            raw_long = data[long_index] & 0xFFFFFFFFFFFFFFFF
            palette_index = (raw_long >> bit_offset) & ((1 << bits) - 1)
            if palette_index >= len(palette):
                return {"Name": "minecraft:air"}, None
            entry = palette[palette_index]

    name = entry.get("Name", "minecraft:air")
    if name in COMMAND_BLOCK_IDS:
        return {"Name": "minecraft:air"}, None

    be = _block_entity_at(chunk, x, y, z)
    return entry, be


def find_data_version(world_dir, x0, z0, x1, z1):
    for x in range(x0, x1 + 1, 16):
        for z in range(z0, z1 + 1, 16):
            chunk = _chunk_at(world_dir, x, z)
            if chunk and "DataVersion" in chunk:
                return chunk["DataVersion"]
    return 4189  # 1.21.10 fallback, only used if the sampled area is fully unloaded


# ---------- minimal stdlib NBT writer (mirrors mca_nbt_dump.py's reader) ----------

TAG_END = 0; TAG_BYTE = 1; TAG_SHORT = 2; TAG_INT = 3; TAG_LONG = 4; TAG_FLOAT = 5
TAG_DOUBLE = 6; TAG_BYTE_ARRAY = 7; TAG_STRING = 8; TAG_LIST = 9; TAG_COMPOUND = 10
TAG_INT_ARRAY = 11; TAG_LONG_ARRAY = 12


class Int:
    """Wrapper so write_payload can tell TAG_Int apart from TAG_Long -- both
    are plain Python ints otherwise."""
    __slots__ = ("v",)
    def __init__(self, v): self.v = v


def infer_tag(v):
    if isinstance(v, Int):
        return TAG_INT
    if isinstance(v, bool):
        return TAG_BYTE
    if isinstance(v, int):
        return TAG_LONG
    if isinstance(v, float):
        return TAG_DOUBLE
    if isinstance(v, str):
        return TAG_STRING
    if isinstance(v, dict):
        return TAG_COMPOUND
    if isinstance(v, list):
        return TAG_LIST
    raise TypeError(f"can't infer NBT tag for {type(v)}")


def write_string(buf, s):
    b = s.encode("utf-8")
    buf.append(struct.pack(">H", len(b)))
    buf.append(b)


def write_payload(buf, tag_type, value, list_item_type=None):
    if tag_type == TAG_BYTE:
        buf.append(struct.pack(">b", int(value)))
    elif tag_type == TAG_SHORT:
        buf.append(struct.pack(">h", int(value)))
    elif tag_type == TAG_INT:
        v = value.v if isinstance(value, Int) else value
        buf.append(struct.pack(">i", int(v)))
    elif tag_type == TAG_LONG:
        buf.append(struct.pack(">q", int(value)))
    elif tag_type == TAG_FLOAT:
        buf.append(struct.pack(">f", float(value)))
    elif tag_type == TAG_DOUBLE:
        buf.append(struct.pack(">d", float(value)))
    elif tag_type == TAG_STRING:
        write_string(buf, value)
    elif tag_type == TAG_COMPOUND:
        for k, v in value.items():
            t = infer_tag(v)
            buf.append(struct.pack(">B", t))
            write_string(buf, k)
            write_payload(buf, t, v)
        buf.append(struct.pack(">B", TAG_END))
    elif tag_type == TAG_LIST:
        item_type = list_item_type if list_item_type is not None else (
            infer_tag(value[0]) if value else TAG_END
        )
        buf.append(struct.pack(">B", item_type))
        buf.append(struct.pack(">i", len(value)))
        for item in value:
            write_payload(buf, item_type, item)
    elif tag_type == TAG_INT_ARRAY:
        buf.append(struct.pack(">i", len(value)))
        for v in value:
            buf.append(struct.pack(">i", v))
    else:
        raise TypeError(f"unsupported top-level write for tag {tag_type}")


def write_nbt_file(path, root_name, root_compound):
    buf = []
    buf.append(struct.pack(">B", TAG_COMPOUND))
    write_string(buf, root_name)
    write_payload(buf, TAG_COMPOUND, root_compound)
    raw = b"".join(buf)
    with gzip.open(path, "wb") as f:
        f.write(raw)


# ---------- structure export ----------

def export_structure(world_dir, x0, y0, z0, x1, y1, z1, out_path):
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    z0, z1 = sorted((z0, z1))
    size = [Int(x1 - x0 + 1), Int(y1 - y0 + 1), Int(z1 - z0 + 1)]

    palette = []  # list of (name, frozenset(props.items()) or None)
    palette_index = {}
    blocks = []

    total = (x1 - x0 + 1) * (y1 - y0 + 1) * (z1 - z0 + 1)
    done = 0
    for y in range(y0, y1 + 1):
        for z in range(z0, z1 + 1):
            for x in range(x0, x1 + 1):
                entry, be = get_block_full(world_dir, x, y, z)
                name = entry.get("Name", "minecraft:air")
                props = entry.get("Properties")
                key = (name, tuple(sorted(props.items())) if props else None)
                if key not in palette_index:
                    palette_index[key] = len(palette)
                    pal_entry = {"Name": name}
                    if props:
                        pal_entry["Properties"] = dict(props)
                    palette.append(pal_entry)
                pidx = palette_index[key]

                block = {
                    "state": Int(pidx),
                    "pos": [Int(x - x0), Int(y - y0), Int(z - z0)],
                }
                if be is not None:
                    nbt = dict(be)
                    nbt.pop("x", None); nbt.pop("y", None); nbt.pop("z", None)
                    if "keepPacked" in nbt:
                        nbt.pop("keepPacked")
                    block["nbt"] = nbt
                blocks.append(block)
                done += 1
        print(f"  y={y} done ({done}/{total})", file=sys.stderr)

    data_version = find_data_version(world_dir, x0, z0, x1, z1)
    root = {
        "DataVersion": Int(data_version),
        "size": size,
        "entities": [],
        "blocks": blocks,
        "palette": palette,
    }
    write_nbt_file(out_path, "", root)
    print(f"wrote {out_path}: {len(blocks)} blocks, {len(palette)} distinct block states, DataVersion={data_version}", file=sys.stderr)


if __name__ == "__main__":
    world_dir = sys.argv[1]
    x0, y0, z0, x1, y1, z1 = (int(a) for a in sys.argv[2:8])
    out_path = sys.argv[8]
    export_structure(world_dir, x0, y0, z0, x1, y1, z1, out_path)
