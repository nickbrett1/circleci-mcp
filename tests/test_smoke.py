"""Smoke test: the src-layout package installs and imports cleanly."""


def test_package_imports():
    import circleci_mcp

    assert circleci_mcp.__version__
