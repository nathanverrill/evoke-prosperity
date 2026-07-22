#!/usr/bin/env python3
"""Full FTP mirror of the Apex Prosperity server into a timestamped local
snapshot: backups/apex/<UTC timestamp>/default/... (backups/ is gitignored).

World saving is frozen over RCON (save-all flush + save-off) for the
duration so region files can't be written mid-transfer, then re-enabled --
same reason a live rsync of a running server isn't trustworthy.

Usage:
    APEX_FTP_PASS='...' python3 scripts/apex_backup.py
Progress: tail -f <snapshot>/backup.log ; final line is
"BACKUP DONE files=N bytes=M" or "BACKUP FAILED: reason".
"""
import ftplib, os, socket, struct, sys, time, traceback

FTP_HOST = "7694.node.apexhosting.gdn"
FTP_USER = "nathanverrill@gmail.com.3277476"
FTP_PASS = os.environ.get("APEX_FTP_PASS") or sys.exit("set APEX_FTP_PASS")
RCON_HOST, RCON_PORT = "98.142.5.162", 25575
RCON_PASS = "MM9xEN5OQszqD5PRGh1plEE8"
ROOT = "/default"

stamp = time.strftime("%Y%m%d-%H%M%SZ", time.gmtime())
dest = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "backups", "apex", stamp)
os.makedirs(dest, exist_ok=True)
log = open(os.path.join(dest, "backup.log"), "a", buffering=1)

def say(msg):
    log.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")

def rcon(cmd):
    def pkt(rid, ptype, body):
        p = struct.pack("<ii", rid, ptype) + body.encode() + b"\x00\x00"
        return struct.pack("<i", len(p)) + p
    s = socket.create_connection((RCON_HOST, RCON_PORT), timeout=15)
    try:
        s.sendall(pkt(1, 3, RCON_PASS))
        ln = struct.unpack("<i", s.recv(4))[0]; s.recv(ln)
        s.sendall(pkt(2, 2, cmd))
        ln = struct.unpack("<i", s.recv(4))[0]
        data = b""
        while len(data) < ln:
            data += s.recv(ln - len(data))
        return data[8:-2].decode(errors="replace")
    finally:
        s.close()

def connect():
    ftp = ftplib.FTP(FTP_HOST, timeout=60)
    ftp.login(FTP_USER, FTP_PASS)
    return ftp

files = bytes_total = 0

def mirror(ftp, remote, local):
    global files, bytes_total
    os.makedirs(local, exist_ok=True)
    entries = []
    ftp.retrlines(f"LIST {remote}", entries.append)
    for line in entries:
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        name = parts[8]
        if name in (".", ".."):
            continue
        rpath, lpath = f"{remote}/{name}", os.path.join(local, name)
        if line.startswith("d"):
            mirror(ftp, rpath, lpath)
        else:
            for attempt in (1, 2, 3):
                try:
                    with open(lpath, "wb") as f:
                        ftp.retrbinary(f"RETR {rpath}", f.write)
                    break
                except Exception as e:
                    say(f"retry {attempt} {rpath}: {e}")
                    if attempt == 3:
                        raise
                    time.sleep(3)
                    ftp = connect()
            files += 1
            bytes_total += os.path.getsize(lpath)
            if files % 200 == 0:
                say(f"{files} files, {bytes_total/1e6:.0f} MB so far")
    return ftp

froze = False
try:
    try:
        say("freezing world saves: " + rcon("save-off"))
        froze = True
        say("flush: " + rcon("save-all flush"))
        time.sleep(5)  # let the flush finish writing
    except Exception as e:
        say(f"RCON freeze unavailable ({e}) -- mirroring live (server may be down, which is also fine)")
    ftp = connect()
    mirror(ftp, ROOT, os.path.join(dest, "default"))
    say(f"BACKUP DONE files={files} bytes={bytes_total}")
except Exception as e:
    say("BACKUP FAILED: " + repr(e))
    traceback.print_exc(file=log)
finally:
    if froze:
        try:
            say("save-on: " + rcon("save-on"))
        except Exception as e:
            say(f"WARNING: could not re-enable saves: {e} -- run RCON save-on manually!")
