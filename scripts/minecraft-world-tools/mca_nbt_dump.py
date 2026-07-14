"""Minimal NBT + Anvil (.mca) region-file reader, stdlib only.

Built for MINECRAFT_WORLD_MAP.md's investigation of the real world saves at
~/evoke-prosperity-files/minecraft/minecraft-world-files/ -- no NBT/Anvil
Python library was installed or needed. This is the foundational parser the
other scripts in this directory (block_at.py, full_command_block_scan.py,
scan_signs.py, scan_chunk_palettes.py, render_slice.py) all import.

Usage as a library:
    from mca_nbt_dump import parse_mca, collect_strings
    for chunk_index, nbt in parse_mca("r.0.0.mca"):
        ...

Run directly for a quick "what entities/kiosks/villagers are in this region
file" pass:
    python3 mca_nbt_dump.py path/to/r.0.0.mca
"""
import sys, struct, zlib, gzip

TAG_END = 0; TAG_BYTE = 1; TAG_SHORT = 2; TAG_INT = 3; TAG_LONG = 4; TAG_FLOAT = 5
TAG_DOUBLE = 6; TAG_BYTE_ARRAY = 7; TAG_STRING = 8; TAG_LIST = 9; TAG_COMPOUND = 10
TAG_INT_ARRAY = 11; TAG_LONG_ARRAY = 12


class Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def u8(self):
        v = self.data[self.pos]; self.pos += 1; return v

    def i8(self):
        """Signed byte -- matters for tags like a chunk section's `Y`,
        which goes negative below world height 0 (two's complement)."""
        v = self.u8()
        return v - 256 if v > 127 else v

    def read(self, n):
        v = self.data[self.pos:self.pos + n]; self.pos += n; return v

    def i16(self):
        return struct.unpack('>h', self.read(2))[0]

    def u16(self):
        return struct.unpack('>H', self.read(2))[0]

    def i32(self):
        return struct.unpack('>i', self.read(4))[0]

    def i64(self):
        return struct.unpack('>q', self.read(8))[0]

    def f32(self):
        return struct.unpack('>f', self.read(4))[0]

    def f64(self):
        return struct.unpack('>d', self.read(8))[0]

    def string(self):
        n = self.u16()
        return self.read(n).decode('utf-8', errors='replace')


def read_tag_payload(r, tag_type):
    if tag_type == TAG_END:
        return None
    elif tag_type == TAG_BYTE:
        return r.i8()
    elif tag_type == TAG_SHORT:
        return r.i16()
    elif tag_type == TAG_INT:
        return r.i32()
    elif tag_type == TAG_LONG:
        return r.i64()
    elif tag_type == TAG_FLOAT:
        return r.f32()
    elif tag_type == TAG_DOUBLE:
        return r.f64()
    elif tag_type == TAG_BYTE_ARRAY:
        n = r.i32(); return r.read(n)
    elif tag_type == TAG_STRING:
        return r.string()
    elif tag_type == TAG_LIST:
        item_type = r.u8()
        n = r.i32()
        return [read_tag_payload(r, item_type) for _ in range(n)]
    elif tag_type == TAG_COMPOUND:
        comp = {}
        while True:
            t = r.u8()
            if t == TAG_END:
                break
            name = r.string()
            comp[name] = read_tag_payload(r, t)
        return comp
    elif tag_type == TAG_INT_ARRAY:
        n = r.i32()
        return [r.i32() for _ in range(n)]
    elif tag_type == TAG_LONG_ARRAY:
        n = r.i32()
        return [r.i64() for _ in range(n)]
    else:
        raise ValueError(f"Unknown tag type {tag_type} at pos {r.pos}")


def parse_nbt(data):
    r = Reader(data)
    t = r.u8()
    if t == TAG_END:
        return None
    name = r.string()
    val = read_tag_payload(r, t)
    return (name, val)


def collect_strings(obj, out):
    """Walk an NBT structure collecting every string value (with its key
    name) -- the cheap way to full-text-search a chunk without knowing its
    shape in advance."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str):
                out.append((k, v))
            else:
                collect_strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_strings(v, out)


def parse_mca(path):
    """Yields (chunk_index, nbt_or_error_string) for every non-empty chunk
    slot (0-1023) in a region file. chunk_index = local_chunk_x +
    local_chunk_z * 32, matching the Anvil format's own header layout."""
    import os
    if os.path.getsize(path) < 8192:
        return []
    with open(path, 'rb') as f:
        header = f.read(8192)
        if len(header) < 8192:
            return []
        results = []
        for i in range(1024):
            off_entry = header[i * 4:i * 4 + 4]
            offset = (off_entry[0] << 16) | (off_entry[1] << 8) | off_entry[2]
            if offset == 0:
                continue
            f.seek(offset * 4096)
            length_bytes = f.read(4)
            if len(length_bytes) < 4:
                continue
            length = struct.unpack('>I', length_bytes)[0]
            comp_type = f.read(1)[0]
            chunk_data = f.read(length - 1)
            try:
                if comp_type == 2:
                    raw = zlib.decompress(chunk_data)
                elif comp_type == 1:
                    raw = gzip.decompress(chunk_data)
                elif comp_type == 3:
                    raw = chunk_data  # uncompressed
                else:
                    continue
            except Exception as e:
                results.append((i, f"DECOMPRESS_ERROR: {e}"))
                continue
            try:
                _name, nbt = parse_nbt(raw)
            except Exception as e:
                results.append((i, f"NBT_PARSE_ERROR: {e}"))
                continue
            results.append((i, nbt))
        return results


if __name__ == '__main__':
    path = sys.argv[1]
    results = parse_mca(path)
    print(f"Parsed {len(results)} non-empty chunk slots from {path}")
    for idx, nbt in results:
        if isinstance(nbt, str):
            print(idx, nbt)
            continue
        strs = []
        collect_strings(nbt, strs)
        interesting = [
            (k, v) for k, v in strs
            if k in ('id', 'CustomName', 'Name', 'identifier')
            or 'villager' in v.lower() or 'kiosk' in v.lower()
            or 'npc' in v.lower() or 'billbot' in v.lower()
        ]
        if interesting:
            print(f"--- chunk slot {idx} ---")
            for k, v in interesting[:50]:
                print(f"   {k} = {v}")
