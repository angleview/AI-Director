"""Reproducible single-image benchmark for an Ultralytics NCNN export."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

def percentile(values: Sequence[float], quantile: float) -> float:
    """Return a linearly interpolated percentile for a non-empty sample."""
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be within [0.0, 1.0]")

    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction

def summarize(values: Sequence[float]) -> dict[str, float | int]:
    """Build compact statistics while retaining raw values elsewhere."""
    if not values:
        raise ValueError("summary requires at least one value")
    numbers = [float(value) for value in values]
    return {
        "count": len(numbers),
        "min": min(numbers),
        "max": max(numbers),
        "mean": statistics.fmean(numbers),
        "p50": percentile(numbers, 0.50),
        "p95": percentile(numbers, 0.95),
        "p99": percentile(numbers, 0.99),
    }

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _run_optional(command: Sequence[str]) -> str | None:
    try:
        completed = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=3
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    output = completed.stdout.strip()
    return output or None


def _cpu_model() -> str | None:
    cpuinfo = Path("/proc/cpuinfo")
    if not cpuinfo.is_file():
        return platform.processor() or None
    for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.lower().startswith("model name"):
            return line.split(":", maxsplit=1)[-1].strip()
    return platform.processor() or None


def _pi_health() -> dict[str, str | None]:
    return {
        "temperature": _run_optional(("vcgencmd", "measure_temp")),
        "throttled": _run_optional(("vcgencmd", "get_throttled")),
    }


def _model_files(model_dir: Path) -> list[Path]:
    required = [model_dir / "model.ncnn.param", model_dir / "model.ncnn.bin"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing NCNN model files: {', '.join(missing)}")
    metadata = model_dir / "metadata.yaml"
    return required + ([metadata] if metadata.is_file() else [])


def _result_measurement(result: Any) -> dict[str, Any]:
    speed = getattr(result, "speed", {}) or {}

    def timing(name: str) -> float | None:
        value = speed.get(name)
        return float(value) if isinstance(value, (int, float)) else None

    boxes = getattr(result, "boxes", None)
    keypoints = getattr(result, "keypoints", None)
    return {
        "preprocess_ms": timing("preprocess"),
        "inference_ms": timing("inference"),
        "postprocess_ms": timing("postprocess"),
        "detections": len(boxes) if boxes is not None else 0,
        "has_keypoints": keypoints is not None,
    }


def _read_image(cv2: Any, source: Path) -> tuple[Any, float]:
    started = time.perf_counter_ns()
    image = cv2.imread(str(source))
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    if image is None:
        raise ValueError(f"OpenCV could not decode input image: {source}")
    return image, elapsed_ms


def run_benchmark(
    model_dir: Path,
    source: Path,
    *,
    warmup: int,
    runs: int,
    imgsz: int,
    confidence: float,
) -> dict[str, Any]:
    if warmup < 0 or runs <= 0:
        raise ValueError("warmup must be non-negative and runs must be positive")
    if imgsz <= 0 or not 0.0 <= confidence <= 1.0:
        raise ValueError("imgsz must be positive and confidence must be within [0.0, 1.0]")
    if not source.is_file():
        raise FileNotFoundError(f"input image does not exist: {source}")
    model_files = _model_files(model_dir)

    import cv2
    from ultralytics import YOLO

    probe, probe_decode_ms = _read_image(cv2, source)
    height, width = probe.shape[:2]

    load_started = time.perf_counter_ns()
    model = YOLO(str(model_dir), task="pose")
    model_load_ms = (time.perf_counter_ns() - load_started) / 1_000_000

    predict_args = {
        "imgsz": imgsz,
        "conf": confidence,
        "verbose": False,
        "save": False,
    }
    for _ in range(warmup):
        image, _ = _read_image(cv2, source)
        model.predict(source=image, **predict_args)

    measurements: list[dict[str, Any]] = []
    health_before = _pi_health()
    for index in range(runs):
        end_to_end_started = time.perf_counter_ns()
        image, decode_ms = _read_image(cv2, source)
        predict_started = time.perf_counter_ns()
        results = model.predict(source=image, **predict_args)
        predict_wall_ms = (time.perf_counter_ns() - predict_started) / 1_000_000
        end_to_end_ms = (time.perf_counter_ns() - end_to_end_started) / 1_000_000
        if not results:
            raise RuntimeError("inference returned no Results object")

        measurement = _result_measurement(results[0])
        stage_values = [measurement[name] for name in (
            "preprocess_ms", "inference_ms", "postprocess_ms"
        )]
        stage_total_ms = (
            sum(stage_values) if all(value is not None for value in stage_values) else None
        )
        measurement.update(
            {
                "run": index + 1,
                "decode_ms": decode_ms,
                "predict_wall_ms": predict_wall_ms,
                "end_to_end_ms": end_to_end_ms,
                "reported_stage_total_ms": stage_total_ms,
                "framework_overhead_ms": (
                    predict_wall_ms - stage_total_ms if stage_total_ms is not None else None
                ),
            }
        )
        measurements.append(measurement)
    health_after = _pi_health()

    timing_names = (
        "decode_ms",
        "preprocess_ms",
        "inference_ms",
        "postprocess_ms",
        "reported_stage_total_ms",
        "framework_overhead_ms",
        "predict_wall_ms",
        "end_to_end_ms",
    )
    summaries = {
        name: summarize([float(item[name]) for item in measurements if item.get(name) is not None])
        for name in timing_names
        if any(item.get(name) is not None for item in measurements)
    }

    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "task": "pose",
            "warmup_runs_excluded": warmup,
            "measured_runs": runs,
            "imgsz": imgsz,
            "confidence": confidence,
            "input_scope": "file_decode_through_results",
        },
        "artifacts": {
            "input": {
                "path": str(source.resolve()),
                "sha256": sha256_file(source),
                "width": width,
                "height": height,
                "probe_decode_ms": probe_decode_ms,
            },
            "model": {
                "path": str(model_dir.resolve()),
                "files": [
                    {
                        "name": path.name,
                        "bytes": path.stat().st_size,
                        "sha256": sha256_file(path),
                    }
                    for path in model_files
                ],
            },
        },
        "environment": {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu": _cpu_model(),
            "python": sys.version.split()[0],
            "packages": {name: _package_version(name) for name in (
                "ultralytics", "ncnn", "opencv-python", "numpy"
            )},
        },
        "setup": {"model_load_ms": model_load_ms},
        "device_health": {"before": health_before, "after": health_after},
        "measurements": measurements,
        "summary_ms": summaries,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True, help="NCNN export directory")
    parser.add_argument("--source", type=Path, required=True, help="fixed input image")
    parser.add_argument("--output", type=Path, required=True, help="raw JSON output path")
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.25)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = run_benchmark(
        args.model,
        args.source,
        warmup=args.warmup,
        runs=args.runs,
        imgsz=args.imgsz,
        confidence=args.conf,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    end_to_end = report["summary_ms"]["end_to_end_ms"]
    inference = report["summary_ms"].get("inference_ms")
    print(f"report: {args.output}")
    print(f"end-to-end p50/p95: {end_to_end['p50']:.2f}/{end_to_end['p95']:.2f} ms")
    if inference is not None:
        print(f"NCNN inference p50/p95: {inference['p50']:.2f}/{inference['p95']:.2f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
