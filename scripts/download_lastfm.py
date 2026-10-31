from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from music_promotion.config import SOURCE_PATH, SOURCE_URL  # noqa: E402


def download(url: str = SOURCE_URL, destination: Path = SOURCE_PATH, force: bool = False) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 1_000_000 and not force:
        print(f"Using existing source file: {destination}")
        return destination

    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "music-promotion-experiment-lab/1.0"},
    )
    print(f"Downloading public Last.fm sample to {destination} ...")
    try:
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        partial.replace(destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise

    if destination.stat().st_size < 1_000_000:
        destination.unlink(missing_ok=True)
        raise RuntimeError("Downloaded file is unexpectedly small; refusing to use it.")
    print(f"Downloaded {destination.stat().st_size / 1_048_576:.1f} MiB.")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the public Last.fm development sample.")
    parser.add_argument("--force", action="store_true", help="Replace an existing source file.")
    args = parser.parse_args()
    download(force=args.force)


if __name__ == "__main__":
    main()
