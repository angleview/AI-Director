"""Resolution-independent control-intent planning."""

from __future__ import annotations

from dataclasses import dataclass

from .domain import (
    ControlAction,
    ControlIntent,
    Decision,
    OperatingMode,
    Perception,
)


@dataclass(frozen=True, slots=True)
class ControllerConfig:
    single_target_y: float = 0.33
    multi_target_y: float = 0.50
    dead_zone_x: float = 0.03
    dead_zone_y: float = 0.04
    pan_gain_degrees: float = 18.0
    tilt_gain_degrees: float = 12.0
    max_step_degrees: float = 4.0
    invert_pan: bool = True
    invert_tilt: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("single_target_y", self.single_target_y),
            ("multi_target_y", self.multi_target_y),
            ("dead_zone_x", self.dead_zone_x),
            ("dead_zone_y", self.dead_zone_y),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0.0, 1.0]")
        if self.pan_gain_degrees < 0 or self.tilt_gain_degrees < 0:
            raise ValueError("controller gains must be non-negative")
        if self.max_step_degrees <= 0:
            raise ValueError("maximum control step must be positive")


class CompositionController:
    def __init__(self, config: ControllerConfig | None = None) -> None:
        self._config = config or ControllerConfig()

    def plan(self, perception: Perception, decision: Decision) -> ControlIntent:
        sequence = perception.frame_sequence
        if decision.reset_requested:
            return ControlIntent(
                frame_sequence=sequence,
                action=ControlAction.RESET,
                reason="reset-gesture-edge",
            )

        if decision.mode not in (OperatingMode.TRACKING, OperatingMode.SHOWCASE):
            return ControlIntent(
                frame_sequence=sequence,
                action=ControlAction.HOLD,
                reason=f"mode-{decision.mode.value.lower()}",
            )

        if not perception.targets:
            return ControlIntent(
                frame_sequence=sequence,
                action=ControlAction.HOLD,
                reason="no-target",
            )

        target_count = len(perception.targets)
        center_x = sum(target.center_x for target in perception.targets) / target_count
        center_y = sum(target.center_y for target in perception.targets) / target_count
        desired_y = (
            self._config.multi_target_y
            if target_count > 1 or decision.mode is OperatingMode.SHOWCASE
            else self._config.single_target_y
        )
        error_x = 0.5 - center_x
        error_y = desired_y - center_y

        if abs(error_x) < self._config.dead_zone_x:
            error_x = 0.0
        if abs(error_y) < self._config.dead_zone_y:
            error_y = 0.0

        pan_delta = error_x * self._config.pan_gain_degrees
        tilt_delta = -error_y * self._config.tilt_gain_degrees
        if self._config.invert_pan:
            pan_delta = -pan_delta
        if self._config.invert_tilt:
            tilt_delta = -tilt_delta

        pan_delta = _clamp(
            pan_delta,
            -self._config.max_step_degrees,
            self._config.max_step_degrees,
        )
        tilt_delta = _clamp(
            tilt_delta,
            -self._config.max_step_degrees,
            self._config.max_step_degrees,
        )

        action = (
            ControlAction.HOLD
            if pan_delta == 0.0 and tilt_delta == 0.0
            else ControlAction.RELATIVE_MOVE
        )
        return ControlIntent(
            frame_sequence=sequence,
            action=action,
            pan_delta_degrees=pan_delta,
            tilt_delta_degrees=tilt_delta,
            reason="composition-error",
        )


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
