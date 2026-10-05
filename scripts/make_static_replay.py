"""Generate a finite MJPEG replay from one checksummed image."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--fps", type=float, default=10.0)
    args = parser.parse_args()
    if args.frames <= 0 or args.fps <= 0:
        parser.error("frames and fps must be positive")
    if args.output.exists():
        parser.error("output already exists; choose a new path to preserve previous results")

    import cv2

    image = cv2.imread(str(args.image))
    if image is None:
        raise ValueError(f"OpenCV could not decode source image: {args.image}")
    height, width = image.shape[:2]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(args.output),
        cv2.VideoWriter_fourcc(*"MJPG"),
        args.fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"OpenCV could not open video writer: {args.output}")
    try:
        for _ in range(args.frames):
            writer.write(image)
    finally:
        writer.release()

    capture = cv2.VideoCapture(str(args.output))
    decoded_frames = 0
    try:
        while True:
            ok, _ = capture.read()
            if not ok:
                break
            decoded_frames += 1
    finally:
        capture.release()
    if decoded_frames != args.frames:
        raise RuntimeError(
            f"generated replay decoded {decoded_frames} frames, expected {args.frames}"
        )

    print(
        json.dumps(
            {
                "output": str(args.output),
                "sha256": sha256_file(args.output),
                "width": width,
                "height": height,
                "fps": args.fps,
                "frames": decoded_frames,
                "duration_seconds": decoded_frames / args.fps,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
