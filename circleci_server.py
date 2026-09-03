#!/usr/bin/env python3
"""Curated CircleCI MCP server for Open WebUI (single, well-described interface).

This is the ONLY CircleCI MCP server exposed to Open WebUI. It intentionally
replaces the generic 156-tool CLI MCP with a small, focused, descriptive set of
tools that use API endpoints verified to work with a normal personal API token.

RULE: use the CircleCI **Insights** API for credit/usage data
(https://circleci.com/docs/api/v2/#tag/Insights) and the standard v2 pipeline
endpoints for run history. Do NOT call the billing endpoints
(/api/v2/organizations/{id}/usage/credits) - they return 404 for an API token.

Auth: reads the `CIRCLE_TOKEN` env var (set in the container).
"""
import json
import os
import urllib.parse
import urllib.request
from mcp.server.fastmcp import FastMCP

BASE = "https://circleci.com/api/v2"
TOKEN = os.environ.get("CIRCLE_TOKEN", "")

mcp = FastMCP("circleci-cost")


def _get(path: str) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}",
        headers={"Circle-Token": TOKEN, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _date_qs(start_date, end_date):
    q = {}
    if start_date:
        q["start-date"] = start_date
    if end_date:
        q["end-date"] = end_date
    return ("?" + urllib.parse.urlencode(q)) if q else ""


@mcp.tool()
def circleci_org_usage_summary(
    org_slug: str = "gh/nickbrett1",
    start_date: str = "",
    end_date: str = "",
) -> dict:
    """Get a CircleCI org's CREDIT / COMPUTE usage for a date range.

    This is the reliable way to get credit usage (uses the CircleCI Insights
    org-summary API). Do NOT use the billing /usage/credits endpoints - they
    404 for an API token.

    Returns:
      - org totals: credits_used, runs, duration_secs, success_rate
      - per-project rows (sorted by credits desc): {project, credits, runs,
        duration_secs, success_rate} - use this to see where spend goes.

    Args:
      org_slug:   e.g. "gh/nickbrett1" (default).
      start_date: "YYYY-MM-DD" inclusive. Omit for trailing 30 days.
      end_date:   "YYYY-MM-DD" inclusive. Omit for trailing 30 days.
    """
    q = _date_qs(start_date, end_date)
    d = _get(f"/insights/{org_slug}/summary{q}")
    org = d.get("org_data", {}).get("metrics", {})
    projects = []
    for p in d.get("org_project_data", []) or []:
        m = p.get("metrics", {})
        projects.append({
            "project": p.get("project_name"),
            "credits": m.get("total_credits_used", 0),
            "runs": m.get("total_runs", 0),
            "duration_secs": m.get("total_duration_secs", 0),
            "success_rate": m.get("success_rate"),
        })
    projects.sort(key=lambda x: x["credits"], reverse=True)
    return {
        "org_slug": org_slug,
        "start_date": start_date or "trailing-30-days",
        "end_date": end_date or "now",
        "org": {
            "credits_used": org.get("total_credits_used", 0),
            "runs": org.get("total_runs", 0),
            "duration_secs": org.get("total_duration_secs", 0),
            "success_rate": org.get("success_rate"),
        },
        "total_credits_used": org.get("total_credits_used", 0),
        "projects": projects,
    }


@mcp.tool()
def circleci_project_workflows(
    project: str,
    start_date: str = "",
    end_date: str = "",
    org_slug: str = "gh/nickbrett1",
) -> dict:
    """Credit/compute usage per WORKFLOW for a single CircleCI project.

    Uses the Insights per-project workflows endpoint. Great for finding WHICH
    workflow/step burns the most credits (e.g. a costly deploy/test job).

    Args:
      project:    repo name, e.g. "ftn".
      start_date: "YYYY-MM-DD". Omit for trailing 30 days.
      end_date:   "YYYY-MM-DD". Omit for trailing 30 days.
    Returns list of {name, total_runs, success_rate, total_credits_used,
      median_credits_used, failed_runs, successful_runs} sorted by credits desc.
    """
    q = _date_qs(start_date, end_date)
    d = _get(f"/insights/{org_slug}/{project}/workflows{q}")
    rows = []
    for it in d.get("items", []) or []:
        m = it.get("metrics", {})
        rows.append({
            "workflow": it.get("name"),
            "total_runs": m.get("total_runs"),
            "successful_runs": m.get("successful_runs"),
            "failed_runs": m.get("failed_runs"),
            "success_rate": m.get("success_rate"),
            "total_credits_used": m.get("total_credits_used"),
            "median_credits_used": m.get("median_credits_used"),
        })
    rows.sort(key=lambda x: (x["total_credits_used"] or 0), reverse=True)
    return {"project": project, "workflows": rows}


@mcp.tool()
def circleci_recent_runs(
    project: str = "",
    limit: int = 10,
    org_slug: str = "gh/nickbrett1",
) -> dict:
    """List the most recent CircleCI pipeline runs (across the org, or one project).

    Returns each run's pipeline number, state (e.g. created/success/failed),
    branch, and commit subject - useful for "what failed / what's running now".

    Args:
      project: repo name to filter to (e.g. "ftn"). Empty = all org projects.
      limit:   max number of runs to return (default 10).
    """
    limit = max(1, min(int(limit), 50))
    if project:
        d = _get(f"/project/{org_slug}/{project}/pipeline")
    else:
        d = _get(f"/pipeline?org-slug={org_slug}")
    runs = []
    for it in d.get("items", []) or []:
        vcs = it.get("vcs", {}) or {}
        commit = vcs.get("commit", {}) or {}
        runs.append({
            "project": it.get("project_slug", "").split("/")[-1],
            "number": it.get("number"),
            "state": it.get("state"),
            "branch": vcs.get("branch"),
            "commit_subject": commit.get("subject"),
            "created_at": it.get("created_at"),
            "updated_at": it.get("updated_at"),
        })
    runs.sort(key=lambda x: x.get("number") or 0, reverse=True)
    return {"org_slug": org_slug, "project": project or "(all)", "runs": runs[:limit]}


@mcp.tool()
def circleci_org_projects(org_slug: str = "gh/nickbrett1") -> list[str]:
    """List the CircleCI project names for an org (e.g. ["ftn", "mailroom", ...]).

    Uses the Insights org-summary response's all_projects field.
    """
    d = _get(f"/insights/{org_slug}/summary")
    return d.get("all_projects", [])


if __name__ == "__main__":
    # Default to stdio (used by mcpo as the child process). Set TRANSPORT to
    # "streamable-http" (with FASTMCP_HOST / FASTMCP_PORT) to serve a native
    # MCP-over-HTTP endpoint. FastMCP ignores FASTMCP_* env vars for host/port
    # (they're passed explicitly at construction), so apply them here.
    transport = os.environ.get("TRANSPORT", "stdio")
    if transport in ("sse", "streamable-http"):
        mcp.settings.host = os.environ.get("FASTMCP_HOST", mcp.settings.host)
        mcp.settings.port = int(os.environ.get("FASTMCP_PORT", mcp.settings.port))
        # FastMCP auto-enables DNS-rebinding protection because the server is
        # constructed with the default host="127.0.0.1" (allow-lists only
        # localhost). That returns 421 for LAN/Mac clients. Disable it so the
        # endpoint is reachable from the NAS LAN like the other MCP servers.
        mcp.settings.transport_security = None
    mcp.run(transport=transport)
