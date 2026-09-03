# CircleCI MCP -> Open WebUI via mcpo (NAS)
#
# Base: mcpo (ghcr.io/open-webui/mcpo) bridges the stdio CircleCI CLI MCP
# server to OpenAPI/Streamable HTTP for Open WebUI. We add the circleci CLI
# binary plus the curated circleci_server.py and config.json so the image is
# fully self-contained (no host bind-mounts) -> reproducible and
# watchtower-updatable on every publish.
FROM ghcr.io/open-webui/mcpo:main

# Link the GHCR package to this repo on push (public repo -> public package).
LABEL org.opencontainers.image.source=https://github.com/nickbrett1/circleci-mcp

# Pin the CLI version; bump this (and re-publish via CircleCI) to update.
ARG CIRCLECI_CLI_VERSION=v1.0.48692

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL -o /tmp/ccli.tgz \
      "https://github.com/CircleCI-Public/circleci-cli/releases/download/${CIRCLECI_CLI_VERSION}/circleci-cli_${CIRCLECI_CLI_VERSION#v}_linux_amd64.tar.gz" \
 && tar xzf /tmp/ccli.tgz -C /usr/local/bin circleci \
 && rm /tmp/ccli.tgz \
 && circleci version

# Curated server + mcpo config baked into the image (replaces host bind-mounts).
COPY config.json /app/config.json
COPY circleci_server.py /app/circleci_server.py
