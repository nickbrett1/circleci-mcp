# circleci-mcp

Curated CircleCI MCP servers for Open WebUI, published to GHCR and auto-updated
by Watchtower. Three MCP servers are baked into the image and exposed together:

| Server          | What it exposes                                                                  |
|-----------------|----------------------------------------------------------------------------------|
| `circleci`      | the **full** native CircleCI CLI MCP (`circleci mcp start`, ~150 tools)          |
| `circleci-cost` | credit/compute usage + run history (4 tools, Insights API)                       |
| `circleci-lite` | narrow run-status + build-log server (3 tools) for day-to-day dev                |

`circleci-cost` and `circleci-lite` are small FastMCP servers written in this
repo, so they stay cheap in model context; `circleci` is the generic CLI MCP for
full control when you need it.

The image is built on `ghcr.io/open-webui/mcpo` (which bridges stdio MCP
servers to OpenAPI/Streamable HTTP) plus the pinned CircleCI CLI binary and this
repo's servers/config, baked into the image (no host mounts).

## Services

Three services run the same image, published by CircleCI to
`ghcr.io/nickbrett1/circleci-mcp` and auto-updated by `watchtower-nick`
(scope `nick`, 60s poll):

| Service              | Port                 | How it serves                                    |
|----------------------|----------------------|--------------------------------------------------|
| `circleci-mcp`       | `127.0.0.1:8767`     | mcpo bridge (OpenAPI/SSE) → Open WebUI           |
| `circleci-cost-mcp`  | `127.0.0.1:8768`     | native Streamable HTTP MCP (`/mcp`) for any client |
| `circleci-lite-mcp`  | `127.0.0.1:8769`     | native Streamable HTTP MCP (`/mcp`) for any client |

## Files

- `Dockerfile` — mcpo base + pinned CircleCI CLI + baked-in servers/config.
- `circleci_server.py` — the curated `circleci-cost` FastMCP server (Insights).
- `circleci_lite_server.py` — the curated `circleci-lite` FastMCP server (run status + build logs).
- `config.json` — mcpo config wiring all three servers.
- `docker-compose.yml` — the three services (NAS deployment).
- `.env.example` — copy to `.env` (NAS-side, never committed) with `CIRCLE_TOKEN`.

## Deploy (NAS)

1. `cp .env.example .env` and set `CIRCLE_TOKEN`.
2. Import `docker-compose.yml` as a Container Manager "Project" (on Synology).
3. On push to `main`, CircleCI publishes `ghcr.io/nickbrett1/circleci-mcp:latest`;
   `watchtower-nick` picks it up within ~60s.

## Code quality / CI

- `.circleci/config.yml` — `build` (ruff + pytest) gating `docker-publish` on `main`.
- Uses the `common` CircleCI context for `GHCR_USERNAME` / `GHCR_TOKEN`.
