"""Exhaustive inventory of every non-empty sign's text in a world save.
full_command_block_scan.py finds command-block logic; this finds the human-
readable signage a command-block scan alone would miss (this is how the
teleport hub's destination labels in MINECRAFT_WORLD_MAP.md §6 were found).

Usage:
    python3 scan_signs.py /path/to/world > signs.txt 2> signs.log
"""
import sys, os, glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mca_nbt_dump import parse_mca


def walk_compounds(obj, out):
    if isinstance(obj, dict):
        if 'id' in obj and isinstance(obj.get('id'), str):
            out.append(obj)
        for v in obj.values():
            walk_compounds(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk_compounds(v, out)


def extract_sign_lines(comp):
    lines = []
    for side in ('front_text', 'back_text'):
        st = comp.get(side)
        if isinstance(st, dict):
            msgs = st.get('messages')
            if isinstance(msgs, list):
                lines.extend(str(m) for m in msgs if m)
    return lines


if __name__ == '__main__':
    world_dir = sys.argv[1]
    region_files = sorted(glob.glob(os.path.join(world_dir, 'region', '*.mca')))
    print(f"Scanning {len(region_files)} region files under {world_dir}", file=sys.stderr)
    count = 0
    for rf in region_files:
        try:
            results = parse_mca(rf)
        except Exception:
            continue
        for idx, nbt in results:
            if isinstance(nbt, str):
                continue
            found = []
            walk_compounds(nbt, found)
            for comp in found:
                cid = comp.get('id', '')
                if 'sign' in cid:
                    x, y, z = comp.get('x'), comp.get('y'), comp.get('z')
                    lines = extract_sign_lines(comp)
                    text = ' | '.join(l for l in lines if l.strip() and l.strip() not in ('""', "''"))
                    if text.strip():
                        count += 1
                        print(f"{x},{y},{z} [{os.path.basename(rf)}] {cid}: {text}")
    print(f"\n{count} non-empty signs total", file=sys.stderr)
