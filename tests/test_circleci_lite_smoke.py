"""Network-free smoke tests for the circleci-lite MCP server module.

These cover import/registration and the pure helpers only -- they never call
the CircleCI API (no CIRCLE_TOKEN, no network), so they're safe in CI and on a
machine without a token. Good as a reference for what the module exposes.
"""

import json
from pathlib import Path

import circleci_lite_server as lite

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_TOOLS = (
    "circleci_lite_recent_runs",
    "circleci_lite_run_status",
    "circleci_lite_failed_job_log",
)


def test_module_imports_with_safe_defaults():
    # CIRCLE_TOKEN is not required at import time; default to empty string.
    assert isinstance(lite.TOKEN, str)
    assert lite.mcp.name == "circleci-lite"


def test_all_three_expected_tools_exist():
    for name in EXPECTED_TOOLS:
        assert callable(getattr(lite, name, None)), f"missing tool: {name}"


def test_slug_joins_org_and_project():
    assert lite._slug("gh/nickbrett1", "pshelf") == "gh/nickbrett1/pshelf"
    assert lite._slug("gh/acme", "circleci-mcp") == "gh/acme/circleci-mcp"


def test_v11_org_maps_github_owner_only():
    # v1.1 uses github/<owner>; v2 uses gh/<owner>. Others pass through.
    assert lite._v11_org("gh/nickbrett1") == "github/nickbrett1"
    assert lite._v11_org("github/nickbrett1") == "github/nickbrett1"
    assert lite._v11_org("bb/nickbrett1") == "bb/nickbrett1"


def test_config_registers_lite_server_with_expected_file():
    cfg = json.loads((REPO_ROOT / "config.json").read_text())
    server = cfg["mcpServers"]["circleci-lite"]
    assert server["command"] == "python3"
    assert server["args"] == ["/app/circleci_lite_server.py"]


def test_dockerfile_bakes_in_lite_server():
    dockerfile = (REPO_ROOT / "Dockerfile").read_text()
    assert "circleci_lite_server.py" in dockerfile
