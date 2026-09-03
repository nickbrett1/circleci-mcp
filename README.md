# circleci-mcp

Curated CircleCI MCP servers for Open WebUI, published to GHCR and auto-updated by Watchtower.

This is the **only** CircleCI MCP surface exposed on the NAS. It intentionally replaces
the generic 156-tool CLI MCP with a small, focused set that uses API endpoints verified to
work with a normal personal API token (the CircleCI **Insights** API for credit/usage data,
plus standard v2 pipeline endpoints for run history).

The published image is built on `ghcr.io/open-webui/mcpo` (which bridges the stdio CircleCI
CLI MCP server to OpenAPI/Streamable HTTP) plus the pinned CircleCI CLI binary and this
repo's curated `circleci_server.py` / `config.json`, baked into the image (no host mounts).

## Services

Two services run the same image, published by CircleCI to `ghcr.io/nickbrett1/circleci-mcp`
and auto-updated by `watchtower-nick` (scope `nick`, 60s poll):

| Service             | Port                 | How it serves                                    |
|---------------------|----------------------|--------------------------------------------------|
| `circleci-mcp`      | `127.0.0.1:8767`     | mcpo bridge (OpenAPI/SSE) → Open WebUI           |
| `circleci-cost-mcp` | `127.0.0.1:8768`     | native Streamable HTTP MCP (`/mcp`) for any client |

## Files

- `Dockerfile` — mcpo base + pinned CircleCI CLI + baked-in server/config.
- `circleci_server.py` — the curated FastMCP server (Insights + pipeline tools).
- `config.json` — mcpo config wiring the CLI MCP and the curated python server.
- `docker-compose.yml` — the two services (NAS deployment).
- `.env.example` — copy to `.env` (NAS-side, never committed) with `CIRCLE_TOKEN`.

## Deploy (NAS)

1. `cp .env.example .env` and set `CIRCLE_TOKEN`.
2. Import `docker-compose.yml` as a Container Manager "Project" (on Synology).
3. On push to `main`, CircleCI publishes `ghcr.io/nickbrett1/circleci-mcp:latest`;
   `watchtower-nick` picks it up within ~60s.

## Code quality / CI

- `.circleci/config.yml` — `build` (ruff + pytest) gating `docker-publish` on `main`.
- Uses the `common` CircleCI context for `GHCR_USERNAME` / `GHCR_TOKEN`.
