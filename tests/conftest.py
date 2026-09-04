"""Pytest fixtures for the circleci-mcp repo.

circleci_lite_server.py lives at the repo root (not inside the installed
src/circleci_mcp package), so this conftest puts the repo root on sys.path so
test modules can import it with a clean top-level import (avoids ruff E402).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
