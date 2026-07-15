# world-seed/

Deliberately empty in git. This is where the real Basin Simulation world
(`basin`, currently ~704MB at `~/evoke-prosperity-files/minecraft/
minecraft-world-files/basin/`) needs to land before building this image
for anything beyond a smoke test — the entrypoint seeds a fresh volume from
whatever's in this directory, and falls back to vanilla world generation if
it's empty (which is how it was verified working in this build pass).

**Not committed here on purpose** — 704MB of region files doesn't belong in a
plain git repo, and `~/evoke-prosperity-files` is itself an uninitialized git
repo with no history, so there's no clean history to preserve anyway. This
needs a deliberate decision, not a `cp`:

- **git-lfs** — keeps it in this repo, versioned, but needs LFS set up and
  everyone who clones understanding LFS bandwidth costs.
- **Pulled from S3 at build/deploy time** — keeps the repo small; the
  Dockerfile or entrypoint would fetch and extract it instead of a `COPY`.
- **Manual placement** — whoever builds the production image drops the world
  here before `docker build`, documented as a runbook step. Fastest to ship,
  easiest to forget.

Until one of these is chosen, this image is fully functional but generates a
fresh vanilla world instead of loading the real Basin Simulation content.
