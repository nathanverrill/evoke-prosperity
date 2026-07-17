# Custom Basin Simulation server: Fabric + Geyser + Floodgate + B1llbot mod.
# Replaces itzg/minecraft-server per BUILD_PLAN.md directive #1 — full version
# control instead of itzg's mod-manager machinery.
#
# Pinned to Minecraft 1.21.11 (not 26.2 -- that was tried and reverted the
# same night: no Yarn or official Mojang mappings exist for 26.2 yet, only
# raw unnamed intermediary, which makes compiling/patching any mod against
# it a real reverse-engineering exercise, not a routine rebuild. 1.21.11 is
# also what the live Apex-hosted server actually runs -- this Dockerfile is
# meant to mirror that, not diverge from it):
#   - Fabric loader 0.19.3, installer 1.1.1.
#   - Base image back to eclipse-temurin:21-jre -- 1.21.11 doesn't need
#     Java 25 the way 26.2 did.
#   - Fabric API 0.141.5+1.21.11, Geyser-Fabric 2.9.6-b1133,
#     Floodgate-Fabric 2.2.6-b60 -- the exact versions confirmed working
#     together on the live Apex server.
#   - B1llbot is a real rebuild (v2.0.0), not the old version-gate patch
#     hack: multi-NPC (config/billbot/npcs.json, checked into this repo --
#     Jim/Beth/Benjamin/Craig/Billbot, each with their own persona/model/
#     location/range), talked to via "@name <message>" from anywhere or
#     normal chat within range of that NPC's real in-world spot. No spawned
#     entity, no in-game config GUI. Source:
#     ~/evoke-prosperity-files/minecraft/billbot_simple_chat_plugins/billbot/
#
# Upgrading any of these is a deliberate diff: bump the ARG, re-verify the
# Modrinth game_versions list actually includes the target Minecraft version
# (filtered to the fabric loader specifically) before changing
# MINECRAFT_VERSION, since Geyser/Floodgate support lags new Minecraft
# releases and often publish other-loader builds under the same project.

FROM eclipse-temurin:21-jre AS downloader

ARG MINECRAFT_VERSION=1.21.11
ARG FABRIC_LOADER_VERSION=0.19.3
ARG FABRIC_INSTALLER_VERSION=1.1.1
ARG FABRIC_API_URL=https://cdn.modrinth.com/data/P7dR8mSH/versions/zGF3drOQ/fabric-api-0.141.5%2B1.21.11.jar
ARG GEYSER_FABRIC_URL=https://cdn.modrinth.com/data/wKkoqHrH/versions/6uw7I3Qj/geyser-fabric-Geyser-Fabric-2.9.6-b1133.jar
ARG FLOODGATE_FABRIC_URL=https://cdn.modrinth.com/data/bWrNNfkb/versions/81EuNxeZ/Floodgate-Fabric-2.2.6-b60.jar

WORKDIR /downloads
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL -o fabric-server-launch.jar \
      "https://meta.fabricmc.net/v2/versions/loader/${MINECRAFT_VERSION}/${FABRIC_LOADER_VERSION}/${FABRIC_INSTALLER_VERSION}/server/jar" \
    && curl -fsSL -o mods/fabric-api.jar --create-dirs "${FABRIC_API_URL}" \
    && curl -fsSL -o mods/geyser-fabric.jar "${GEYSER_FABRIC_URL}" \
    && curl -fsSL -o mods/floodgate-fabric.jar "${FLOODGATE_FABRIC_URL}" \
    && test -s fabric-server-launch.jar \
    && test -s mods/fabric-api.jar \
    && test -s mods/geyser-fabric.jar \
    && test -s mods/floodgate-fabric.jar

FROM eclipse-temurin:21-jre

RUN groupadd -r minecraft && useradd -r -g minecraft -m minecraft
WORKDIR /server

COPY --from=downloader /downloads/fabric-server-launch.jar /server/fabric-server-launch.jar
COPY --from=downloader /downloads/mods/ /server/mods/
COPY mods/billbot-2.0.0.jar /server/mods/billbot-2.0.0.jar
COPY config/ /server/config/
COPY datapacks/ /server/world-datapacks/
COPY server.properties.template /server/server.properties.template
COPY entrypoint.sh /server/entrypoint.sh
# world-seed/ is intentionally NOT baked in with a plain COPY (see
# world-seed/README.md) -- for local/manual use it's populated on the host
# before build and copied in below; this COPY is a no-op if the directory is
# empty, matching the documented "falls back to vanilla generation" behavior.
COPY world-seed/ /server/world-seed/
# world-data must exist and be minecraft-owned in the image layer before VOLUME
# is declared, or a fresh named volume gets created root-owned on first mount
# and the non-root minecraft user can't write into it.
RUN mkdir -p /server/world-data \
    && chmod +x /server/entrypoint.sh \
    && chown -R minecraft:minecraft /server

VOLUME ["/server/world-data"]

# 25565 Java, 19132/udp Bedrock (Geyser), 25575 RCON
EXPOSE 25565 19132/udp 25575

USER minecraft
ENTRYPOINT ["/server/entrypoint.sh"]
