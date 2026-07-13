# Custom Basin Simulation server: Fabric + Geyser + Floodgate + B1llbot mod.
# Replaces itzg/minecraft-server per BUILD_PLAN.md directive #1 — full version
# control instead of itzg's mod-manager machinery.
#
# All versions below are pinned deliberately and verified working together as of
# this build (fetched and checksum-verified from meta.fabricmc.net / Modrinth):
#   - Minecraft 26.2 (Mojang's post-1.21 year.minor versioning scheme — this is
#     genuinely the current stable release name, not a typo), Fabric loader
#     0.19.3, installer 1.1.1 — confirmed meta.fabricmc.net serves a server jar
#     for this exact loader/installer/game-version combination.
#   - Base image bumped from eclipse-temurin:21-jre to :25-jre — 26.2's server
#     jar is compiled to class file version 69 (Java 25); booting it under
#     Java 21 fails immediately with UnsupportedClassVersionError, discovered
#     by actually starting the container, not just resolving the jar URLs.
#   - Fabric API 0.154.2+26.2 — latest Modrinth build tagged for game version
#     26.2 specifically.
#   - Geyser-Fabric 2.11.0-b1196, Floodgate-Fabric 2.2.6-b67 — both confirmed
#     via Modrinth's game_versions tagging (filtered to loaders containing
#     "fabric" — both projects also publish Velocity/NeoForge/Spigot builds
#     under the same project, so grabbing "the latest version" without
#     filtering by loader silently grabs the wrong platform's jar). Floodgate
#     is NOT distributed through GeyserMC's own download API for Fabric (that
#     API only lists bungee/spigot/velocity) — it's a separate Modrinth project
#     (GeyserMC/Floodgate-Modded) for modded platforms. Easy to miss.
#   - The B1llbot mod is DROPPED from this build, not upgraded. Its
#     fabric.mod.json version gate ("minecraft": "~1.21.10") is easy to patch
#     (see the disabled RUN step below, kept for when this is revisited), but
#     patching it and actually booting the server surfaced a real, deeper
#     problem: the mod's compiled bytecode was remapped against 1.21.10's
#     intermediary mappings, and its entrypoint class fails to resolve at
#     runtime (NoClassDefFoundError: net.minecraft.class_2561) on 26.2's
#     different intermediary mapping set. Fixing this needs a real recompile
#     against 26.2 — and Fabric hasn't published Yarn mappings for 26.2 yet
#     (checked meta.fabricmc.net/v2/versions/yarn/26.2: zero builds; this
#     version was released essentially the same day as this change). Nothing
#     to patch around — re-add the mod once Yarn mappings for 26.2 exist
#     (typically days to a couple weeks after a release) and the mod's source
#     (~/evoke-prosperity-files/minecraft/billbot_simple_chat_plugins/billbot/)
#     can actually be rebuilt against them. This only affects B1llbot's
#     in-Minecraft chat presence -- the web app's B1llbot (Hub drawer,
#     Companion Mode, #/billbot) is a completely separate integration
#     (OpenWebUI + Ollama, see evoke-infra/openwebui-bootstrap.py) and is
#     unaffected by this gap.
# Upgrading any of these is a deliberate diff: bump the ARG, re-verify the
# Modrinth game_versions list actually includes the target Minecraft version
# (filtered to the fabric loader specifically) before changing
# MINECRAFT_VERSION, since Geyser/Floodgate support lags new Minecraft
# releases and often publish other-loader builds under the same project.

FROM eclipse-temurin:25-jre AS downloader

ARG MINECRAFT_VERSION=26.2
ARG FABRIC_LOADER_VERSION=0.19.3
ARG FABRIC_INSTALLER_VERSION=1.1.1
ARG FABRIC_API_URL=https://cdn.modrinth.com/data/P7dR8mSH/versions/Kr4WG5mG/fabric-api-0.154.2%2B26.2.jar
ARG GEYSER_FABRIC_URL=https://cdn.modrinth.com/data/wKkoqHrH/versions/6TIwzcQR/Geyser-Fabric-2.11.0-b1196.jar
ARG FLOODGATE_FABRIC_URL=https://cdn.modrinth.com/data/bWrNNfkb/versions/urOFTrVX/Floodgate-Fabric-2.2.6-b67.jar

WORKDIR /downloads
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates zip unzip \
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

# Patch B1llbot's fabric.mod.json version constraint (see the note above) --
# done here rather than hand-editing the jar checked into the repo, so the
# original third-party artifact stays untouched and this transformation is
# visible in the build, not silently baked into a binary.
COPY mods/billbot-1.0.1.jar /downloads/billbot-original.jar
RUN mkdir -p /tmp/billbot-patch && cd /tmp/billbot-patch \
    && unzip -q /downloads/billbot-original.jar fabric.mod.json \
    && sed -i 's/"minecraft": "~1.21.10"/"minecraft": "*"/' fabric.mod.json \
    && cp /downloads/billbot-original.jar /downloads/billbot-patched.jar \
    && zip -q /downloads/billbot-patched.jar fabric.mod.json

FROM eclipse-temurin:25-jre

RUN groupadd -r minecraft && useradd -r -g minecraft -m minecraft
WORKDIR /server

COPY --from=downloader /downloads/fabric-server-launch.jar /server/fabric-server-launch.jar
COPY --from=downloader /downloads/mods/ /server/mods/
# billbot-patched.jar deliberately NOT copied into /server/mods/ -- see the
# top-of-file note. Re-add this line once Yarn mappings for 26.2 exist and
# the mod's been rebuilt (patching the manifest alone isn't enough).
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
