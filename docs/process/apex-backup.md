# Backing up the Apex Minecraft server

Full, versioned, local snapshots of the live Prosperity server (world +
mods + config + everything), taken over FTP by `scripts/apex_backup.py`.
First snapshot: `backups/apex/20260722-173007Z/` (1.8 GB, 1,451 files,
~7 minutes), taken 2026-07-22 right after the watchdog-crash repair
session.

## How to run one

```sh
APEX_FTP_PASS='<the Apex account password>' python3 scripts/apex_backup.py
```

That's the whole procedure. Each run creates a new UTC-timestamped
snapshot directory:

```
backups/apex/<YYYYMMDD-HHMMSSZ>/default/   ← full mirror of the server
├── basin/            world: level.dat, region/ (218 files), playerdata/,
│                     datapacks/ (the live copies of the repo packs)
├── mods/             billbot, fabric-api, Geyser, Floodgate, savs-common-economy
├── config/           incl. savs-common-economy/shops.json + balances.json
├── server.properties, logs/, crash-reports/, ...everything else
```

- The password is **not stored anywhere** — it comes from the
  `APEX_FTP_PASS` env var each run (same password as the Apex panel;
  see `docs/process/billbot-npc-status.md` for the FTP account details).
- `backups/` is **gitignored** — snapshots never enter the repo. The
  script itself is committed and contains no secrets.
- Budget ~2 GB of disk per snapshot; prune old ones by deleting their
  timestamp directory.

## Watching progress / knowing it worked

The script runs in the foreground (wrap in `nohup ... &` to detach).
It logs to `<snapshot>/backup.log`; follow with:

```sh
tail -f backups/apex/*/backup.log
```

The **final line is the verdict**: `BACKUP DONE files=N bytes=M` or
`BACKUP FAILED: <reason>`. A snapshot without a `BACKUP DONE` line is
incomplete — delete it and rerun.

Sanity numbers for a good snapshot (as of 2026-07-22): ~1,450 files,
~1.8 GB, `basin/region/` has 218 files, `mods/` has 5 jars.

## Consistency: stopped vs. live server

- **Best**: stop the server from the Apex panel first. Files are frozen,
  the mirror is perfect. (FTP keeps working while the server is down.)
- **Fine**: run against the live server. The script freezes world writes
  first over RCON (`save-off` + `save-all flush`), mirrors, then
  re-enables saving (`save-on`) — even if the mirror fails midway.
- If the script logs `WARNING: could not re-enable saves`, run RCON
  `save-on` manually (RCON coordinates are in the root `.env`:
  `MINECRAFT_BRIDGE_*`).

## Restoring

There is no automated restore (deliberately — restoring a live server
should be a decision, not a script accident). To restore:

1. **Stop the server** in the Apex panel.
2. FTP the needed files from the snapshot back to the same paths under
   `default/` (host `7694.node.apexhosting.gdn`, port 21). For a full
   world restore that's the `basin/` directory; for a single mangled
   file (a datapack function, `shops.json`, a playerdata file) just that
   file — playerdata restores only work while the player is offline.
3. Start the server from the panel.

## If the FTP host has changed

Apex migrations change the node hostname and can change ports (it
happened 2026-07-22: `6689.node` → `7694.node`, game port 25756 → 25714).
If login fails, get the current FTP host/username from the Apex panel and
update the constants at the top of `scripts/apex_backup.py` — and expect
to update `.env` (`MINECRAFT_PUBLIC_*`, `MINECRAFT_BRIDGE_*`) at the same
time, since the game/RCON endpoints will have moved too.

## When to take one

- Before and after any raw command-block surgery in the live world (the
  world save is the *only* copy of that state — datapacks are in git,
  physical blocks are not).
- Before Apex-side maintenance (jar/version changes, migrations).
- After sessions that change world state you'd hate to lose (like the
  2026-07-22 repair: entity-pileup cleanup, disabled rogue command
  blocks, economy state).
