#!/bin/bash
set -euo pipefail

# Fabric resolves mods/ and reads server.properties/eula.txt relative to the
# process's working directory (the "game directory"), not relative to wherever
# fabric-server-launch.jar lives. So the working directory has to BE the
# persistent volume, and mods/ (image content, not runtime state) gets
# symlinked in fresh on every boot rather than copied — that way an image
# rebuild (new mod version) takes effect on restart without touching the world.
WORLD_DATA=/server/world-data
LEVEL_NAME="${LEVEL_NAME:-world}"

if [ "${EULA:-false}" != "true" ]; then
  echo "Set EULA=true (https://account.mojang.com/documents/minecraft_eula) to run this server." >&2
  exit 1
fi

mkdir -p "$WORLD_DATA"
cd "$WORLD_DATA"

echo "eula=true" > eula.txt

# mods/ is always the image's current content — never copied into the volume,
# so it can't go stale across image rebuilds.
rm -rf mods
ln -s /server/mods mods

# The world itself persists across restarts and image rebuilds; only seed it
# from the image's baked-in world-seed/ the first time the volume is empty.
if [ ! -d "$LEVEL_NAME" ] && [ -d /server/world-seed ] && [ -n "$(ls -A /server/world-seed 2>/dev/null)" ]; then
  echo "No existing '$LEVEL_NAME' world in the volume; seeding from baked-in world-seed/"
  mkdir -p "$LEVEL_NAME"
  cp -r /server/world-seed/. "$LEVEL_NAME/"
fi

# Datapacks are project content (this repo), not world state — sync fresh on
# every boot so a datapack fix ships without touching the world itself.
mkdir -p "$LEVEL_NAME/datapacks"
cp -r /server/world-datapacks/. "$LEVEL_NAME/datapacks/"

# Mod config (e.g. billbot's config/billbot/npcs.json) is also project
# content, not world state -- Fabric reads config/ relative to this working
# directory ($WORLD_DATA), not /server/config where the image bakes it in,
# so it has to be synced here the same way datapacks are, every boot.
mkdir -p config
cp -r /server/config/. config/

# server.properties is config, not state — regenerated from the template on
# every boot from env vars, never hand-edited on disk.
sed \
  -e "s|__LEVEL_NAME__|${LEVEL_NAME}|g" \
  -e "s|__MOTD__|${MOTD:-EVOKE Prosperity - Basin Simulation}|g" \
  -e "s|__RCON_PASSWORD__|${RCON_PASSWORD:?RCON_PASSWORD must be set}|g" \
  -e "s|__MAX_PLAYERS__|${MAX_PLAYERS:-40}|g" \
  /server/server.properties.template > server.properties

# Geyser's config: the Bedrock listener/Floodgate auth-type settings are fixed
# by this deployment, but Floodgate generates a key.pem here on first run that
# must persist — so template it in only if missing, same pattern as the world.
mkdir -p config
if [ ! -f config/config.yml ]; then
  cat > config/config.yml <<EOF
bedrock:
  address: 0.0.0.0
  port: 19132
  clone-remote-port: false
remote:
  address: 127.0.0.1
  port: 25565
  auth-type: floodgate
  use-proxy-protocol: false
floodgate-key-file: key.pem
EOF
fi

exec java -Xmx${JAVA_MAX_MEMORY:-4G} -jar /server/fabric-server-launch.jar nogui
