#!/usr/bin/env python3
"""circleci-lite: a deliberately narrow CircleCI MCP server for day-to-day dev.

Exposes just enough to answer the two things you reach for while developing:

  1. "what's the run status?"  -> recent runs, and a run's full status
     (pipeline -> workflows -> jobs, with each job's state).
  2. "why did it fail?"        -> the failing job's log tail.

It intentionally exposes a handful of tools instead of the full ~150-tool
native CLI MCP (exposed separately as the `circleci` server), so it stays cheap
in model context.

Auth: reads the `CIRCLE_TOKEN` env var (set in the container). Run/workflow/job
status uses the CircleCI v2 REST API; job output/logs use the v1.1 API. Both
accept a normal personal API token.
"""
import json
import os
import urllib.error
import urllib.request
from typing import Optional

from mcp.server.fastmcp import FastMCP

V2 = "https://circleci.com/api/v2"
V11 = "https://circleci.com/api/v1.1"
TOKEN = os.environ.get("CIRCLE_TOKEN", "")

mcp = FastMCP("circleci-lite")


def _slug(org_slug: str, project: str) -> str:
    return f"{org_slug}/{project}"


def _get(base: str, path: str):
    req = urllib.request.Request(
        f"{base}{path}",
        headers={"Circle-Token": TOKEN, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}: {e.read().decode()[:300]}"}
    except Exception as e:  # noqa: BLE001
        return {"_error": f"request failed: {e}"}


def _v11_org(org_slug: str) -> str:
    """Map a v2 org slug (gh/x) to the v1.1 owner form (github/x)."""
    if org_slug.startswith("gh/") or org_slug.startswith("github/"):
        return "github/" + org_slug.split("/")[-1]
    return org_slug  # bitbucket / others pass through


def _resolve_pipeline(project: str, pipeline_number: Optional[int], org_slug: str):
    d = _get(V2, f"/project/{_slug(org_slug, project)}/pipeline")
    if "_error" in d or not d.get("items"):
        return None
    items = d["items"]
    if pipeline_number is None:
        return items[0]
    return next((p for p in items if p.get("number") == pipeline_number), None)


def _run_workflows(pipeline_id: str) -> list:
    d = _get(V2, f"/pipeline/{pipeline_id}/workflow")
    if "_error" in d:
        return [{"_error": d["_error"]}]
    out = []
    for w in d.get("items") or []:
        wf = {"name": w.get("name"), "status": w.get("status")}
        jd = _get(V2, f"/workflow/{w['id']}/job")
        if "_error" in jd:
            wf["jobs"] = [{"_error": jd["_error"]}]
        else:
            wf["jobs"] = [
                {
                    "job_number": j.get("job_number"),
                    "name": j.get("name"),
                    "status": j.get("status"),
                }
                for j in (jd.get("items") or [])
            ]
        out.append(wf)
    return out


def _job_output_text(project: str, job_number: int, org_slug: str) -> str:
    org = _v11_org(org_slug)
    d = _get(V11, f"/project/{org}/{project}/{job_number}/output")
    if isinstance(d, dict) and "_error" in d:
        return f"<error: {d['_error']}>"
    if isinstance(d, list):
        parts = []
        for block in d:
            if isinstance(block, dict) and block.get("message"):
                parts.append(str(block["message"]))
        return "\n".join(parts)
    return json.dumps(d)


def _first_failed_job(project: str, pipeline_number: Optional[int], org_slug: str):
    pipe = _resolve_pipeline(project, pipeline_number, org_slug)
    if pipe is None:
        return None, None
    for wf in _run_workflows(pipe["id"]):
        for j in wf.get("jobs") or []:
            if j.get("status") == "failed":
                return j, pipe
    return None, pipe


@mcp.tool()
def circleci_lite_recent_runs(
    project: str = "",
    limit: int = 8,
    org_slug: str = "gh/nickbrett1",
) -> dict:
    """Recent pipeline runs -- CircleCI's "what's building / what just ran".

    Returns each run's number, state, branch and commit subject for the given
    project, or across the whole org when `project` is empty.

    Args:
      project: repo name to filter to (e.g. "pshelf"). Empty = all org projects.
      limit:   max runs to return (1..25, default 8).
      org_slug: e.g. "gh/nickbrett1" (default).
    """
    try:
        limit = max(1, min(int(limit), 25))
    except (TypeError, ValueError):
        limit = 8
    if project:
        d = _get(V2, f"/project/{_slug(org_slug, project)}/pipeline")
    else:
        d = _get(V2, f"/pipeline?org-slug={org_slug}")
    if "_error" in d:
        return d
    runs = []
    for it in (d.get("items") or [])[:limit]:
        vcs = it.get("vcs") or {}
        commit = vcs.get("commit") or {}
        runs.append(
            {
                "project": (it.get("project_slug") or "").split("/")[-1],
                "number": it.get("number"),
                "state": it.get("state"),
                "branch": vcs.get("branch"),
                "commit_subject": commit.get("subject"),
                "created_at": it.get("created_at"),
            }
        )
    return {"project": project or "(all org)", "runs": runs}


@mcp.tool()
def circleci_lite_run_status(
    project: str,
    pipeline_number: Optional[int] = None,
    org_slug: str = "gh/nickbrett1",
) -> dict:
    """Full status of one pipeline run (or the most recent run of `project`).

    Returns the pipeline state plus every workflow and job in it with each
    job's state (success / failed / running / ...). `pipeline_number` is the
    run number from `circleci_lite_recent_runs`; omit it to use the latest run.

    Args:
      project: repo name, e.g. "pshelf".
      pipeline_number: optional run number to inspect.
      org_slug: e.g. "gh/nickbrett1" (default).
    """
    pipe = _resolve_pipeline(project, pipeline_number, org_slug)
    if pipe is None:
        return {
            "error": f"no pipeline found for project {project!r} (number={pipeline_number})"
        }
    return {
        "project": project,
        "pipeline_number": pipe.get("number"),
        "pipeline_state": pipe.get("state"),
        "branch": (pipe.get("vcs") or {}).get("branch"),
        "created_at": pipe.get("created_at"),
        "workflows": _run_workflows(pipe["id"]),
    }


@mcp.tool()
def circleci_lite_failed_job_log(
    project: str,
    job_number: Optional[int] = None,
    pipeline_number: Optional[int] = None,
    lines: int = 120,
    org_slug: str = "gh/nickbrett1",
) -> dict:
    """Return the log tail for a CircleCI job -- the "why did the build fail?" tool.

    - If `job_number` is given, fetch that job's log directly.
    - Otherwise find the first FAILED job in `project`'s most recent run (or the
      run identified by `pipeline_number`) and return that job's log tail.

    `lines` controls how many trailing lines to return (10..500, default 120) to
    keep the output small in model context.

    Returns: {project, job_number, job_name, source, lines: [ ...tail... ]}
    """
    try:
        lines = max(10, min(int(lines), 500))
    except (TypeError, ValueError):
        lines = 120
    job_name = None
    if job_number is None:
        job, pipe = _first_failed_job(project, pipeline_number, org_slug)
        if pipe is None:
            return {"error": f"no pipeline found for project {project!r}"}
        if job is None:
            return {
                "info": f"pipeline #{pipe.get('number')} has no FAILED job",
                "pipeline_state": pipe.get("state"),
            }
        job_number = job["job_number"]
        job_name = job.get("name")
    text = _job_output_text(project, job_number, org_slug)
    return {
        "project": project,
        "job_number": job_number,
        "job_name": job_name,
        "source": f"v1.1 /project/{_v11_org(org_slug)}/{project}/{job_number}/output",
        "lines": text.splitlines()[-lines:],
    }


if __name__ == "__main__":
    # Default to stdio (used by mcpo as the child process). Set TRANSPORT to
    # "streamable-http" (with FASTMCP_HOST / FASTMCP_PORT) to serve a native
    # MCP-over-HTTP endpoint. Disable DNS-rebinding protection so the endpoint
    # is reachable from the NAS LAN like the other MCP servers.
    transport = os.environ.get("TRANSPORT", "stdio")
    if transport in ("sse", "streamable-http"):
        mcp.settings.host = os.environ.get("FASTMCP_HOST", mcp.settings.host)
        mcp.settings.port = int(os.environ.get("FASTMCP_PORT", mcp.settings.port))
        mcp.settings.transport_security = None
    mcp.run(transport=transport)
