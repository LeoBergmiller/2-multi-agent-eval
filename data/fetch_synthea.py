"""Download the pinned Synthea jar and verify its checksum.

The jar is ~200MB and gitignored. It is a build input, not source.

**The checksum is the reproducibility control, not the tag.** Synthea's only rolling
release is `master-branch-latest`, and even the versioned `v4.0.0` release reports
`immutable: false` — GitHub permits its assets to be replaced in place. A jar that
changed underneath us would not error; it would generate a different population from
the same seed, and every human-verified `ground_truth` would silently become wrong
while `make data` still reported success. So the digest is checked on every fetch and
a mismatch is fatal.
"""

from __future__ import annotations

import hashlib
import logging
import sys
import urllib.request
from pathlib import Path

from synthea_spec import (
    SYNTHEA_JAR_BYTES,
    SYNTHEA_JAR_SHA256,
    SYNTHEA_JAR_URL,
    SYNTHEA_VERSION,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent
SYNTHEA_DIR = DATA_DIR / "synthea"
JAR_PATH = SYNTHEA_DIR / "synthea-with-dependencies.jar"

_CHUNK = 1 << 20


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path: Path) -> None:
    """Raise unless `path` is byte-for-byte the pinned jar."""
    actual = sha256_of(path)
    if actual != SYNTHEA_JAR_SHA256:
        raise ValueError(
            f"Checksum mismatch for {path}.\n"
            f"  expected sha256 {SYNTHEA_JAR_SHA256}\n"
            f"  actual   sha256 {actual}\n"
            "The pinned Synthea release is not immutable on GitHub, so this means "
            "either a corrupted download or a replaced asset. Do NOT generate data "
            "from it: the population would differ from the one every verified "
            "ground_truth was computed against. Delete the file and re-fetch; if it "
            "still mismatches, the upstream asset changed and the pin in "
            "data/synthea_spec.py needs a human decision."
        )
    logger.info("checksum OK (%s)", SYNTHEA_JAR_SHA256[:16])


def fetch(force: bool = False) -> Path:
    SYNTHEA_DIR.mkdir(parents=True, exist_ok=True)

    if JAR_PATH.is_file() and not force:
        logger.info("jar already present at %s", JAR_PATH)
        verify(JAR_PATH)
        return JAR_PATH

    logger.info(
        "downloading Synthea %s (~%d MB)", SYNTHEA_VERSION, SYNTHEA_JAR_BYTES // 10**6
    )
    logger.info("  %s", SYNTHEA_JAR_URL)
    tmp = JAR_PATH.with_suffix(".jar.part")
    try:
        with urllib.request.urlopen(SYNTHEA_JAR_URL) as response, tmp.open("wb") as out:
            while chunk := response.read(_CHUNK):
                out.write(chunk)
        # Verify BEFORE moving into place, so a bad download never becomes the jar
        # that `make data` silently picks up on the next run.
        verify(tmp)
        tmp.replace(JAR_PATH)
    finally:
        tmp.unlink(missing_ok=True)

    logger.info("wrote %s", JAR_PATH)
    return JAR_PATH


def main() -> int:
    force = "--force" in sys.argv
    try:
        fetch(force=force)
    except (OSError, ValueError):
        logger.exception("synthea jar fetch failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
