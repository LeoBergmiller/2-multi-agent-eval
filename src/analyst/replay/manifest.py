"""What the committed cassettes were recorded against.

A cassette replays faithfully forever — that is its job. What it cannot do is notice
that the world it recorded no longer exists. After Gate 1a step 2 the committed
cassettes still replay a fixture-era answer of 37 while the warehouse they nominally
describe now returns 133, and nothing in a replayed run was able to say so: the run
succeeded, the metric mismatched, and "the metric mismatched" is indistinguishable from
"the agent got it wrong."

Those are different states and deserve different verdicts. This module records the
dataset identity at RECORD time so a replayed run can compare it against the identity
committed in the repo, and report **STALE** rather than **FAIL** when they disagree.

Both sides are committed, so the check works on a clean clone with no warehouse:
`data/warehouse_version.txt` is written by `make data` and committed;
`cassettes/manifest.json` is written by a RECORD run and committed. An absent manifest
means the cassettes predate this mechanism — which is exactly the fixture era.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from analyst.contracts import Contract
from analyst.replay import store

#: Marker used when the cassettes predate the manifest entirely.
FIXTURE_ERA = "fixture-era"


class CassetteManifest(Contract):
    """Identity of the data the committed cassettes were recorded against."""

    warehouse_version: str
    corpus_version: str
    recorded_at: str
    git_sha: str = "unknown"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def warehouse_version_path() -> Path:
    return _repo_root() / "data" / "warehouse_version.txt"


def manifest_path() -> Path:
    """Derived from `cassettes_root()`, deliberately.

    The manifest belongs to the cassettes and must move with them. Computing it from
    the repo root instead let the RECORD-path test — which monkeypatches
    `cassettes_root` precisely so it cannot touch the committed cassettes — write a
    real manifest anyway. That silently flipped `make demo` from STALE to FAIL by
    asserting the cassettes matched the current warehouse when they did not: a
    hygiene leak whose only symptom was a *different wrong verdict*.

    Called as `store.cassettes_root()` rather than imported by name: a
    `from ... import cassettes_root` binds the function at import time, so
    `monkeypatch.setattr("analyst.replay.store.cassettes_root", ...)` would never
    reach it and the leak would survive the fix that was supposed to close it.
    """
    return store.cassettes_root() / "manifest.json"


def current_warehouse_version() -> str:
    """The dataset identity committed in the repo.

    Written by `make data` from the pinned Synthea parameters, not read from the
    `.duckdb` file — the warehouse is gitignored, and a check that only worked after
    a 200MB download and a generation run would not run where it matters.
    """
    path = warehouse_version_path()
    if not path.is_file():
        return FIXTURE_ERA
    return path.read_text().strip()


def read_manifest() -> CassetteManifest | None:
    path = manifest_path()
    if not path.is_file():
        return None
    return CassetteManifest.model_validate_json(path.read_text())


def write_manifest(warehouse_version: str, corpus_version: str, git_sha: str) -> Path:
    path = manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = CassetteManifest(
        warehouse_version=warehouse_version,
        corpus_version=corpus_version,
        recorded_at=datetime.now(UTC).isoformat(timespec="seconds"),
        git_sha=git_sha,
    )
    path.write_text(json.dumps(manifest.model_dump(), indent=2, sort_keys=True) + "\n")
    return path


def staleness_note() -> str | None:
    """A human-readable reason the cassettes are stale, or None if they are current.

    Returns a note rather than a bool so the verdict line can say *what* drifted.
    """
    current = current_warehouse_version()
    manifest = read_manifest()

    if manifest is None:
        return (
            "cassettes predate the cassette manifest, so they were recorded against "
            f"the deleted CSV fixtures; the warehouse is now {current}"
        )
    if manifest.warehouse_version != current:
        return (
            f"cassettes were recorded against warehouse {manifest.warehouse_version}, "
            f"but the committed warehouse is now {current}"
        )
    return None
