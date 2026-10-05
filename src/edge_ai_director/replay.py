"""Offline video replay through the real pose backend and virtual actuator."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from time import monotonic_ns
from typing import Any

from .benchmark import sha256_file, summarize
from .control import CompositionController
from .domain import Frame, PipelineResult
from .pipeline import SynchronousPipeline
from .simulated import VirtualActuator
from .state_machine import DirectorStateMachine
from .ultralytics_backend import PoseBackendConfig, UltralyticsPoseBackend


class OpenCVVideoSource:
    """Read every frame from a finite video in original order."""

    def __init__(
        self,
        path: Path | str,
        *,
        cv2_module: Any | None = None,
        clock_ns: Callable[[], int] = monotonic_ns,
    ) -> None:
        if cv2_module is None:
            import cv2 as cv2_module

        self._path = Path(path)
        self._capture = cv2_module.VideoCapture(str(self._path))
        if not self._capture.isOpened():
            self._capture.release()
            raise ValueError(f"OpenCV could not open replay video: {self._path}")
        self._clock_ns = clock_ns
        self._sequence = 0
        self._closed = False

    def read(self) -> Frame | None:
        if self._closed:
            return None
        ok, image = self._capture.read()
        if not ok:
            self.close()
            return None
        height, width = image.shape[:2]
        frame = Frame(
            sequence=self._sequence,
            captured_at_ns=self._clock_ns(),
            width=int(width),
            height=int(height),
            payload=image,
        )
        self._sequence += 1
        return frame

    def close(self) -> None:
        if not self._closed:
            self._capture.release()
            self._closed = True

    def __enter__(self) -> OpenCVVideoSource:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _record(result: PipelineResult, position: tuple[float, float]) -> dict[str, Any]:
    return {
        "type": "frame",
        "sequence": result.frame.sequence,
        "mode": result.decision.mode.value,
        "target_count": result.decision.target_count,
        "gesture": result.perception.gesture.value,
        "gesture_edge": result.decision.gesture_edge.value,
        "intent": {
            "action": result.intent.action.value,
            "pan_delta_degrees": result.intent.pan_delta_degrees,
            "tilt_delta_degrees": result.intent.tilt_delta_degrees,
            "reason": result.intent.reason,
        },
        "virtual_position_degrees": {"pan": position[0], "tilt": position[1]},
        "timings_ms": {
            "capture": result.timings.capture_ms,
            "inference": result.timings.inference_ms,
            "decision": result.timings.decision_ms,
            "actuation": result.timings.actuation_ms,
            "total": result.timings.total_ms,
            "frame_age": result.timings.frame_age_ms,
        },
    }


def run_replay(
    *,
    video: Path,
    model: Path,
    output: Path,
    limit: int | None,
    config: PoseBackendConfig,
) -> dict[str, Any]:
    actuator = VirtualActuator()
    output.parent.mkdir(parents=True, exist_ok=True)
    total_samples: list[float] = []
    started_ns = time.perf_counter_ns()
    processed = 0

    with OpenCVVideoSource(video) as source, output.open("w", encoding="utf-8") as stream:
        backend = UltralyticsPoseBackend(model, config=config)
        pipeline = SynchronousPipeline(
            source=source,
            backend=backend,
            state_machine=DirectorStateMachine(started_at_ns=monotonic_ns()),
            controller=CompositionController(),
            actuator=actuator,
        )
        header = {
            "type": "metadata",
            "schema_version": 1,
            "video": str(video.resolve()),
            "video_sha256": sha256_file(video),
            "model": str(model.resolve()),
            "configuration": {
                "confidence": config.confidence,
                "imgsz": config.imgsz,
                "min_area_ratio": config.min_area_ratio,
                "max_targets": config.max_targets,
                "limit": limit,
            },
        }
        stream.write(json.dumps(header, ensure_ascii=False) + "\n")
        for result in pipeline.run(limit=limit):
            processed += 1
            total_samples.append(result.timings.total_ms)
            stream.write(json.dumps(_record(result, actuator.position), ensure_ascii=False) + "\n")

        elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
        summary = {
            "type": "summary",
            "processed_frames": processed,
            "run_wall_ms": elapsed_ms,
            "pipeline_total_ms": summarize(total_samples) if total_samples else None,
            "final_virtual_position_degrees": {
                "pan": actuator.position[0],
                "tilt": actuator.position[1],
            },
        }
        stream.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.50)
    parser.add_argument("--min-area", type=float, default=0.03)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.limit is not None and args.limit < 0:
        raise SystemExit("--limit must be non-negative")
    summary = run_replay(
        video=args.video,
        model=args.model,
        output=args.output,
        limit=args.limit,
        config=PoseBackendConfig(
            confidence=args.conf,
            imgsz=args.imgsz,
            min_area_ratio=args.min_area,
        ),
    )
    print(f"processed frames: {summary['processed_frames']}")
    print(f"report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
