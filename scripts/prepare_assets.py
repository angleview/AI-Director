"""Verify bundled NCNN files and download the checksummed public input.

Stdlib only. No model inference, shell execution or hardware access.
Existing files are never overwritten. Downloads require HTTPS and a matching
manifest hash before the temporary file is installed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify(path: Path, expected_hash: str, expected_bytes: int | None = None) -> None:
    if not path.is_file():
        raise ValueError(f"missing file: {path.name}")
    if expected_bytes is not None and path.stat().st_size != expected_bytes:
        raise ValueError(f"size mismatch: {path.name}")
    if digest(path) != expected_hash:
        raise ValueError(f"SHA-256 mismatch: {path.name}; existing file was not overwritten")


def verify_model() -> None:
    manifest = json.loads((ROOT / "assets/models/manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        verify(ROOT / manifest["directory"] / item["name"], item["sha256"], item["bytes"])
        print(f"verified model: {item['name']}")


def download_verified(
    destination: Path, urls: list[str], expected_hash: str, *, max_bytes: int = 10_000_000
) -> None:
    if destination.exists():
        verify(destination, expected_hash)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    errors = []
    for url in urls:
        if not url.startswith("https://"):
            raise ValueError("asset URLs must use HTTPS")
        temporary: Path | None = None
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "AI-Director-assets/1"})
            with urllib.request.urlopen(request, timeout=30) as response:
                if not response.geturl().startswith("https://"):
                    raise ValueError("refusing a non-HTTPS redirect")
                with tempfile.NamedTemporaryFile(
                    dir=destination.parent, suffix=".download", delete=False
                ) as output:
                    temporary = Path(output.name)
                    size = 0
                    while chunk := response.read(64 * 1024):
                        size += len(chunk)
                        if size > max_bytes:
                            raise ValueError("asset exceeded download size limit")
                        output.write(chunk)
            verify(temporary, expected_hash)
            # Hard-link creation fails if another process created destination:
            # unlike replace(), it never overwrites existing user data.
            destination.hardlink_to(temporary)
            return
        except (OSError, ValueError) as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    raise RuntimeError("no verified input downloaded: " + "; ".join(errors))


def prepare_input() -> None:
    manifest = json.loads((ROOT / "assets/inputs/manifest.json").read_text(encoding="utf-8"))
    item = manifest["assets"][0]
    destination = ROOT / "assets/inputs" / item["local_filename"]
    download_verified(destination, [item["source_url"], *item.get("mirrors", [])], item["sha256"])
    print(f"verified input: assets/inputs/{item['local_filename']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["model", "input", "all"])
    args = parser.parse_args()
    if args.action in ("model", "all"):
        verify_model()
    if args.action in ("input", "all"):
        prepare_input()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
