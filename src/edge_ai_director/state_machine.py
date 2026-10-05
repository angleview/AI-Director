"""Deterministic operating-mode transitions for the director."""

from __future__ import annotations

from dataclasses import dataclass

from .domain import Decision, Gesture, OperatingMode, Perception


_NS_PER_SECOND = 1_000_000_000


@dataclass(frozen=True, slots=True)
class StateMachineConfig:
    patrol_after_seconds: float = 5.0
    privacy_after_seconds: float = 30.0
    showcase_hold_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.patrol_after_seconds < 0:
            raise ValueError("patrol timeout must be non-negative")
        if self.privacy_after_seconds <= self.patrol_after_seconds:
            raise ValueError("privacy timeout must be greater than patrol timeout")
        if self.showcase_hold_seconds < 0:
            raise ValueError("showcase hold time must be non-negative")


class DirectorStateMachine:
    """Owns mode transitions and converts level gestures into edge events."""

    def __init__(
        self,
        *,
        started_at_ns: int,
        config: StateMachineConfig | None = None,
    ) -> None:
        if started_at_ns < 0:
            raise ValueError("start timestamp must be non-negative")
        self._config = config or StateMachineConfig()
        self._started_at_ns = started_at_ns
        self._last_target_at_ns: int | None = None
        self._showcase_started_at_ns: int | None = None
        self._previous_gesture = Gesture.NONE
        self._mode = OperatingMode.SEARCHING

    @property
    def mode(self) -> OperatingMode:
        return self._mode

    def update(self, perception: Perception, *, now_ns: int) -> Decision:
        if now_ns < self._started_at_ns:
            raise ValueError("state-machine time cannot move before its start")

        has_target = bool(perception.targets)
        if has_target:
            self._last_target_at_ns = now_ns
            if self._mode in (OperatingMode.SEARCHING, OperatingMode.PRIVACY):
                self._mode = OperatingMode.TRACKING

        gesture_edge = Gesture.NONE
        if (
            perception.gesture is not Gesture.NONE
            and perception.gesture is not self._previous_gesture
        ):
            gesture_edge = perception.gesture

        reset_requested = gesture_edge is Gesture.BOTH_HANDS_UP
        if gesture_edge is Gesture.LEFT_HAND_UP:
            if self._mode is OperatingMode.LOCKED:
                self._mode = OperatingMode.TRACKING
            else:
                self._mode = OperatingMode.LOCKED

        if self._mode is OperatingMode.SHOWCASE and not (
            has_target and perception.showcase_pose
        ):
            self._mode = OperatingMode.TRACKING
            self._showcase_started_at_ns = None
        elif self._mode is OperatingMode.TRACKING and has_target and perception.showcase_pose:
            if self._showcase_started_at_ns is None:
                self._showcase_started_at_ns = now_ns
            hold_ns = int(self._config.showcase_hold_seconds * _NS_PER_SECOND)
            if now_ns - self._showcase_started_at_ns >= hold_ns:
                self._mode = OperatingMode.SHOWCASE
        elif not perception.showcase_pose:
            self._showcase_started_at_ns = None

        if self._mode not in (OperatingMode.LOCKED, OperatingMode.SHOWCASE) and not has_target:
            reference_ns = self._last_target_at_ns or self._started_at_ns
            missing_ns = now_ns - reference_ns
            privacy_ns = int(self._config.privacy_after_seconds * _NS_PER_SECOND)
            patrol_ns = int(self._config.patrol_after_seconds * _NS_PER_SECOND)
            if missing_ns >= privacy_ns:
                self._mode = OperatingMode.PRIVACY
            elif missing_ns >= patrol_ns:
                self._mode = OperatingMode.SEARCHING

        self._previous_gesture = perception.gesture
        return Decision(
            mode=self._mode,
            target_count=len(perception.targets),
            gesture_edge=gesture_edge,
            reset_requested=reset_requested,
        )
