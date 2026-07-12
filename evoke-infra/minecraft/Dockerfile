# Custom Basin Simulation server: Fabric + Geyser + Floodgate + B1llbot mod.
# Replaces itzg/minecraft-server per BUILD_PLAN.md directive #1 — full version
# control instead of itzg's mod-manager machinery.
#
# All versions below are pinned deliberately and verified working together as of
# this build (fetched and checksum-verified from meta.fabricmc.net / Modrinth):
#   - Minecraft 1.21.10, Fabric loader 0.16.10 — matches the B1llbot mod's own
#     gradle.properties pin exactly (~/evoke-prosperity-files/minecraft/
#     billbot_simple_chat_plugins/billbot/gradle.properties).
#   - Fabric API 0.138.4+1.21.10 — same pin as the mod's build dependency.
#   - Geyser-Fabric 2.9.2-b1008, Floodgate-Fabric 2.2.6-b51 — both confirmed via
#     Modrinth's game_versions tagging to support 1.21.10 specifically. Floodgate
#     is NOT distributed through GeyserMC's own download API for Fabric (that API
#     only lists bungee/spigot/velocity) — it's a separate Modrinth project
#     (GeyserMC/Floodgate-Modded) for modded platforms. Easy to miss.
# Upgrading any of these is a deliberate diff: bump the ARG, re-verify the
# Modrinth game_versions list actually includes the target Minecraft version
# before changing MINECRAFT_VERSION, since Geyser/Floodgate support lags new
# Minecraft releases.

FROM eclipse-temurin:21-jre AS downloader

ARG MINECRAFT_VERSION=1.21.10
# NOTE: deliberately newer than the B1llbot mod's own gradle.properties pin
# (0.16.10) — that version is too old for the current Fabric API/Geyser-Fabric
# builds, which require Fabric Loader >=0.17.0/>=0.17.2 respectively. Verified
# working: the mod itself doesn't hard-pin an exact loader version (only
# "fabric-api @ [*]"), so it loads fine against a newer loader.
ARG FABRIC_LOADER_VERSION=0.19.3
ARG FABRIC_INSTALLER_VERSION=1.1.1
ARG FABRIC_API_URL=https://cdn.modrinth.com/data/P7dR8mSH/versions/tV4Gc0Zo/fabric-api-0.138.4%2B1.21.10.jar
ARG GEYSER_FABRIC_URL=https://cdn.modrinth.com/data/wKkoqHrH/versions/ahzEdvn0/geyser-fabric-Geyser-Fabric-2.9.2-b1008.jar
ARG FLOODGATE_FABRIC_URL=https://cdn.modrinth.com/data/bWrNNfkb/versions/QFAMeMNB/Floodgate-Fabric-2.2.6-b51.jar

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
COPY mods/billbot-1.0.1.jar /server/mods/billbot-1.0.1.jar
COPY datapacks/ /server/world-datapacks/
COPY server.properties.template /server/server.properties.template
COPY entrypoint.sh /server/entrypoint.sh
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
