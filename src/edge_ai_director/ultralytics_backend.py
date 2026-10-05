"""Ultralytics/NCNN adapter that emits dependency-free domain values."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import monotonic_ns
from typing import Any

from .domain import Frame, Gesture, Perception, TargetObservation


@dataclass(frozen=True, slots=True)
class PoseBackendConfig:
    confidence: float = 0.50
    imgsz: int = 640
    min_area_ratio: float = 0.03
    max_targets: int = 2
    showcase_hand_distance_ratio: float = 0.125

    def __post_init__(self) -> None:
        for name, value in (
            ("confidence", self.confidence),
            ("min_area_ratio", self.min_area_ratio),
            ("showcase_hand_distance_ratio", self.showcase_hand_distance_ratio),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0.0, 1.0]")
        if self.imgsz <= 0 or self.max_targets <= 0:
            raise ValueError("imgsz and max_targets must be positive")


@dataclass(frozen=True, slots=True)
class _Candidate:
    target: TargetObservation
    keypoints: Sequence[Sequence[float]]


class UltralyticsPoseBackend:
    """Run pose inference and isolate framework objects at the adapter boundary."""

    def __init__(
        self,
        model_path: Path | str | None = None,
        *,
        config: PoseBackendConfig | None = None,
        model: Any | None = None,
        clock_ns: Callable[[], int] = monotonic_ns,
    ) -> None:
        if model is None:
            if model_path is None:
                raise ValueError("model_path is required when model is not injected")
            from ultralytics import YOLO

            model = YOLO(str(model_path), task="pose")
        self._model = model
        self._config = config or PoseBackendConfig()
        self._clock_ns = clock_ns

    def infer(self, frame: Frame) -> Perception:
        if frame.payload is None:
            raise ValueError("pose inference requires an image payload")
        results = self._model.predict(
            source=frame.payload,
            imgsz=self._config.imgsz,
            conf=self._config.confidence,
            verbose=False,
            save=False,
        )
        if not results:
            raise RuntimeError("pose inference returned no Results object")

        candidates = _extract_candidates(
            results[0],
            width=frame.width,
            height=frame.height,
            min_area_ratio=self._config.min_area_ratio,
        )
        candidates.sort(key=lambda candidate: candidate.target.area_ratio, reverse=True)
        selected = candidates[: self._config.max_targets]

        gesture = Gesture.NONE
        showcase_pose = False
        if selected:
            gesture, showcase_pose = _pose_signals(
                selected[0].keypoints,
                width=frame.width,
                height=frame.height,
                showcase_distance_ratio=self._config.showcase_hand_distance_ratio,
            )
        return Perception(
            frame_sequence=frame.sequence,
            completed_at_ns=self._clock_ns(),
            targets=tuple(candidate.target for candidate in selected),
            gesture=gesture,
            showcase_pose=showcase_pose,
        )


def _extract_candidates(
    result: Any,
    *,
    width: int,
    height: int,
    min_area_ratio: float,
) -> list[_Candidate]:
    boxes_object = getattr(result, "boxes", None)
    if boxes_object is None:
        return []
    boxes = _to_list(getattr(boxes_object, "xywh", []))
    confidences = _to_list(getattr(boxes_object, "conf", []))
    keypoints_object = getattr(result, "keypoints", None)
    keypoints = (
        _to_list(getattr(keypoints_object, "xy", [])) if keypoints_object is not None else []
    )

    frame_area = float(width * height)
    candidates: list[_Candidate] = []
    for index, box in enumerate(boxes):
        if len(box) < 4:
            continue
        center_x, center_y, box_width, box_height = (float(value) for value in box[:4])
        area_ratio = max(0.0, min(1.0, box_width * box_height / frame_area))
        if area_ratio < min_area_ratio:
            continue
        person_keypoints = keypoints[index] if index < len(keypoints) else []
        target_x, target_y = _tracking_point(person_keypoints, center_x, center_y)
        confidence = float(confidences[index]) if index < len(confidences) else 0.0
        candidates.append(
            _Candidate(
                target=TargetObservation(
                    center_x=_normalise(target_x, width),
                    center_y=_normalise(target_y, height),
                    area_ratio=area_ratio,
                    confidence=max(0.0, min(1.0, confidence)),
                ),
                keypoints=person_keypoints,
            )
        )
    return candidates


def _tracking_point(
    keypoints: Sequence[Sequence[float]], fallback_x: float, fallback_y: float
) -> tuple[float, float]:
    left_eye = _point(keypoints, 1)
    right_eye = _point(keypoints, 2)
    if _visible(left_eye) and _visible(right_eye):
        return (
            (left_eye[0] + right_eye[0]) / 2.0,
            (left_eye[1] + right_eye[1]) / 2.0,
        )
    nose = _point(keypoints, 0)
    return nose if _visible(nose) else (fallback_x, fallback_y)


def _pose_signals(
    keypoints: Sequence[Sequence[float]],
    *,
    width: int,
    height: int,
    showcase_distance_ratio: float,
) -> tuple[Gesture, bool]:
    nose = _point(keypoints, 0)
    left_eye = _point(keypoints, 1)
    left_wrist = _point(keypoints, 9)
    right_wrist = _point(keypoints, 10)

    both_up = (
        _visible(nose)
        and _visible(left_wrist)
        and _visible(right_wrist)
        and left_wrist[1] < nose[1]
        and right_wrist[1] < nose[1]
    )
    left_up = (
        _visible(left_eye) and _visible(left_wrist) and left_wrist[1] < left_eye[1]
    )
    gesture = Gesture.BOTH_HANDS_UP if both_up else (
        Gesture.LEFT_HAND_UP if left_up else Gesture.NONE
    )

    hands_below_face = (
        _visible(nose)
        and _visible(left_wrist)
        and _visible(right_wrist)
        and left_wrist[1] > nose[1]
        and right_wrist[1] > nose[1]
    )
    normalised_distance = math.hypot(
        (left_wrist[0] - right_wrist[0]) / width,
        (left_wrist[1] - right_wrist[1]) / height,
    )
    showcase_pose = hands_below_face and normalised_distance < showcase_distance_ratio
    return gesture, showcase_pose


def _point(values: Sequence[Sequence[float]], index: int) -> tuple[float, float]:
    if index >= len(values) or len(values[index]) < 2:
        return 0.0, 0.0
    return float(values[index][0]), float(values[index][1])


def _visible(point: tuple[float, float]) -> bool:
    return point[0] > 0.0 and point[1] > 0.0


def _normalise(value: float, dimension: int) -> float:
    return max(0.0, min(1.0, value / dimension))


def _to_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    if hasattr(value, "tolist"):
        value = value.tolist()
    return list(value)
