"""Deterministic adapters used for learning, testing, and replay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .domain import ControlAction, ControlIntent, Frame, Perception


class ReplayFrameSource:
    def __init__(self, frames: Iterable[Frame]) -> None:
        self._frames = iter(frames)

    def read(self) -> Frame | None:
        return next(self._frames, None)


class ScriptedInferenceBackend:
    """Returns known observations instead of executing a neural network."""

    def __init__(self, perceptions: Mapping[int, Perception]) -> None:
        self._perceptions = dict(perceptions)

    def infer(self, frame: Frame) -> Perception:
        try:
            perception = self._perceptions[frame.sequence]
        except KeyError as exc:
            raise KeyError(f"no scripted perception for frame {frame.sequence}") from exc
        if perception.frame_sequence != frame.sequence:
            raise ValueError("perception belongs to a different frame")
        return perception


@dataclass(frozen=True, slots=True)
class ActuationRecord:
    frame_sequence: int
    action: ControlAction
    requested_pan_delta_degrees: float
    requested_tilt_delta_degrees: float
    applied_pan_degrees: float
    applied_tilt_degrees: float
    clipped: bool


class VirtualActuator:
    """Applies limits in memory and records every ordered intent."""

    def __init__(
        self,
        *,
        pan_limits: tuple[float, float] = (-90.0, 90.0),
        tilt_limits: tuple[float, float] = (-90.0, 90.0),
        reset_pan: float = 0.0,
        reset_tilt: float = -90.0,
    ) -> None:
        _validate_limits("pan", pan_limits, reset_pan)
        _validate_limits("tilt", tilt_limits, reset_tilt)
        self._pan_limits = pan_limits
        self._tilt_limits = tilt_limits
        self._reset_pan = reset_pan
        self._reset_tilt = reset_tilt
        self._pan = reset_pan
        self._tilt = reset_tilt
        self._records: list[ActuationRecord] = []

    @property
    def records(self) -> tuple[ActuationRecord, ...]:
        return tuple(self._records)

    @property
    def position(self) -> tuple[float, float]:
        return self._pan, self._tilt

    def apply(self, intent: ControlIntent) -> None:
        requested_pan = self._pan
        requested_tilt = self._tilt
        if intent.action is ControlAction.RESET:
            requested_pan = self._reset_pan
            requested_tilt = self._reset_tilt
        elif intent.action is ControlAction.RELATIVE_MOVE:
            requested_pan += intent.pan_delta_degrees
            requested_tilt += intent.tilt_delta_degrees

        applied_pan = _clamp(requested_pan, self._pan_limits)
        applied_tilt = _clamp(requested_tilt, self._tilt_limits)
        clipped = applied_pan != requested_pan or applied_tilt != requested_tilt
        self._pan = applied_pan
        self._tilt = applied_tilt
        self._records.append(
            ActuationRecord(
                frame_sequence=intent.frame_sequence,
                action=intent.action,
                requested_pan_delta_degrees=intent.pan_delta_degrees,
                requested_tilt_delta_degrees=intent.tilt_delta_degrees,
                applied_pan_degrees=self._pan,
                applied_tilt_degrees=self._tilt,
                clipped=clipped,
            )
        )


def _validate_limits(name: str, limits: tuple[float, float], reset: float) -> None:
    if limits[0] >= limits[1]:
        raise ValueError(f"{name} limits must be increasing")
    if not limits[0] <= reset <= limits[1]:
        raise ValueError(f"{name} reset position must be inside its limits")


def _clamp(value: float, limits: tuple[float, float]) -> float:
    return max(limits[0], min(limits[1], value))
