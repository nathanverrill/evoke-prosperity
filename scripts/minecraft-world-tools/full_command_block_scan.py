"""Exhaustive inventory of every command block and spawner in a world save
-- no keyword filter, every region file. This is how MINECRAFT_WORLD_MAP.md
§3-6 (the real minigames, the Halyard economy, the teleport hub) were found:
a first keyword-filtered pass missed real content (e.g. the mob-arena
question in §10's history), so this scans everything and lets you grep the
output afterward instead of guessing keywords up front.

Usage:
    python3 full_command_block_scan.py /path/to/world > scan.txt 2> scan.log

On a ~700MB world (218 region files) this takes a couple of minutes; watch
scan.log for progress.
"""
import sys, os, glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mca_nbt_dump import parse_mca


def walk_compounds(obj, out):
    """Collect every dict in the tree that looks like a block entity (has
    a string 'id') -- command blocks and spawners are both this shape."""
    if isinstance(obj, dict):
        if 'id' in obj and isinstance(obj.get('id'), str):
            out.append(obj)
        for v in obj.values():
            walk_compounds(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk_compounds(v, out)


if __name__ == '__main__':
    world_dir = sys.argv[1]
    region_files = sorted(glob.glob(os.path.join(world_dir, 'region', '*.mca')))
    print(f"Scanning {len(region_files)} region files under {world_dir}", file=sys.stderr)

    all_command_blocks = []
    all_spawners = []
    other_ids = {}

    for rf in region_files:
        try:
            results = parse_mca(rf)
        except Exception as e:
            print(f"FAILED to parse {rf}: {e}", file=sys.stderr)
            continue
        for idx, nbt in results:
            if isinstance(nbt, str):
                continue
            found = []
            walk_compounds(nbt, found)
            for comp in found:
                cid = comp.get('id', '')
                if cid in ('minecraft:command_block', 'minecraft:chain_command_block', 'minecraft:repeating_command_block'):
                    x, y, z = comp.get('x'), comp.get('y'), comp.get('z')
                    cmd = comp.get('Command', '')
                    auto = comp.get('auto')
                    powered = comp.get('powered')
                    all_command_blocks.append((x, y, z, cmd, auto, powered, os.path.basename(rf)))
                elif cid in ('minecraft:mob_spawner', 'minecraft:spawner'):
                    x, y, z = comp.get('x'), comp.get('y'), comp.get('z')
                    spawn_data = comp.get('SpawnData')
                    spawn_potentials = comp.get('SpawnPotentials')
                    all_spawners.append((x, y, z, spawn_data, spawn_potentials, os.path.basename(rf)))
                else:
                    other_ids[cid] = other_ids.get(cid, 0) + 1
        print(f"  done {os.path.basename(rf)} -- running total {len(all_command_blocks)} command blocks, {len(all_spawners)} spawners", file=sys.stderr)

    print(f"\n=== TOTAL: {len(all_command_blocks)} command blocks, {len(all_spawners)} spawners across {len(region_files)} region files ===\n")

    print("--- All command blocks (x,y,z | auto | powered | file | command) ---")
    for x, y, z, cmd, auto, powered, rf in sorted(all_command_blocks, key=lambda t: (t[0] or 0, t[2] or 0)):
        print(f"{x},{y},{z} | auto={auto} powered={powered} | {rf} | {cmd}")

    print("\n--- All spawners ---")
    for x, y, z, spawn_data, spawn_potentials, rf in all_spawners:
        print(f"{x},{y},{z} | {rf} | SpawnData={spawn_data} | SpawnPotentials={spawn_potentials}")

    print("\n--- Other block-entity ids seen (counts) ---")
    for k, v in sorted(other_ids.items(), key=lambda kv: -kv[1]):
        print(f"  {v:5d}  {k}")
