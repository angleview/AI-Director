"""Domain values shared by the pipeline stages.

The types in this module deliberately contain no OpenCV, NCNN, Flask, or
ServoKit imports.  Keeping them dependency-free makes the system behaviour
testable on any machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OperatingMode(str, Enum):
    SEARCHING = "SEARCHING"
    TRACKING = "TRACKING"
    SHOWCASE = "SHOWCASE"
    LOCKED = "LOCKED"
    PRIVACY = "PRIVACY"


class Gesture(str, Enum):
    NONE = "NONE"
    LEFT_HAND_UP = "LEFT_HAND_UP"
    BOTH_HANDS_UP = "BOTH_HANDS_UP"


class ControlAction(str, Enum):
    HOLD = "HOLD"
    RELATIVE_MOVE = "RELATIVE_MOVE"
    RESET = "RESET"


@dataclass(frozen=True, slots=True)
class Frame:
    """One captured image plus identity and timing metadata."""

    sequence: int
    captured_at_ns: int
    width: int
    height: int
    payload: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("frame sequence must be non-negative")
        if self.captured_at_ns < 0:
            raise ValueError("capture timestamp must be non-negative")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("frame dimensions must be positive")


@dataclass(frozen=True, slots=True)
class TargetObservation:
    """A target location expressed in resolution-independent coordinates."""

    center_x: float
    center_y: float
    area_ratio: float
    confidence: float

    def __post_init__(self) -> None:
        for name, value in (
            ("center_x", self.center_x),
            ("center_y", self.center_y),
            ("area_ratio", self.area_ratio),
            ("confidence", self.confidence),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0.0, 1.0]")


@dataclass(frozen=True, slots=True)
class Perception:
    """Inference output associated with exactly one input frame."""

    frame_sequence: int
    completed_at_ns: int
    targets: tuple[TargetObservation, ...] = ()
    gesture: Gesture = Gesture.NONE
    showcase_pose: bool = False

    def __post_init__(self) -> None:
        if self.frame_sequence < 0:
            raise ValueError("perception frame sequence must be non-negative")
        if self.completed_at_ns < 0:
            raise ValueError("perception timestamp must be non-negative")


@dataclass(frozen=True, slots=True)
class Decision:
    mode: OperatingMode
    target_count: int
    gesture_edge: Gesture = Gesture.NONE
    reset_requested: bool = False


@dataclass(frozen=True, slots=True)
class ControlIntent:
    """A requested action, not proof that physical movement occurred."""

    frame_sequence: int
    action: ControlAction
    pan_delta_degrees: float = 0.0
    tilt_delta_degrees: float = 0.0
    reason: str = ""


@dataclass(frozen=True, slots=True)
class StageTimings:
    capture_ms: float
    inference_ms: float
    decision_ms: float
    actuation_ms: float
    total_ms: float
    frame_age_ms: float


@dataclass(frozen=True, slots=True)
class PipelineResult:
    frame: Frame
    perception: Perception
    decision: Decision
    intent: ControlIntent
    timings: StageTimings
