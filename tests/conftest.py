"""Tests that need files this repository can't include are skipped.

Some tests use real mod and game files (USSEP's BSAs, the game's behavior
files, other people's modpacks) that can't be redistributed. Put them in
tests/fixtures/ussep, tests/fixtures/havok or private-test-data/ (next to
this repository's root, see tests/README.md) and those tests run too.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ("fixtures/ussep", "fixtures\\ussep", "fixtures/havok", "fixtures\\havok",
           "private-test-data", "ussep", "USSEP", "havok")
NEEDS = [ROOT / "tests" / "fixtures" / "ussep", ROOT / "tests" / "fixtures" / "havok"]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.failed and call.excinfo is not None and not all(p.exists() for p in NEEDS):
        text = str(rep.longrepr)
        if any(k in text for k in PRIVATE):
            rep.outcome = "skipped"
            rep.longrepr = (str(item.fspath), item.location[1] or 0,
                            "Skipped: needs test files that can't be redistributed (see tests/README.md)")
