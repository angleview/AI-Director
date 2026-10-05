"""Run the complete core with deterministic inputs and no external hardware."""

from __future__ import annotations

import json

from .control import CompositionController
from .domain import Frame, Gesture, Perception, TargetObservation
from .pipeline import SynchronousPipeline
from .simulated import ReplayFrameSource, ScriptedInferenceBackend, VirtualActuator
from .state_machine import DirectorStateMachine


class StepClock:
    def __init__(self, *, start_ns: int, step_ns: int = 1_000_000) -> None:
        self._now_ns = start_ns
        self._step_ns = step_ns

    def __call__(self) -> int:
        value = self._now_ns
        self._now_ns += self._step_ns
        return value


def main() -> None:
    start_ns = 1_000_000_000
    frames = tuple(
        Frame(
            sequence=sequence,
            captured_at_ns=start_ns + sequence * 5_000_000,
            width=640,
            height=360,
        )
        for sequence in range(7)
    )
    target = TargetObservation(
        center_x=0.72,
        center_y=0.45,
        area_ratio=0.18,
        confidence=0.92,
    )
    gestures = (
        Gesture.NONE,
        Gesture.NONE,
        Gesture.LEFT_HAND_UP,
        Gesture.LEFT_HAND_UP,
        Gesture.NONE,
        Gesture.LEFT_HAND_UP,
        Gesture.BOTH_HANDS_UP,
    )
    perceptions = {
        frame.sequence: Perception(
            frame_sequence=frame.sequence,
            completed_at_ns=frame.captured_at_ns + 2_000_000,
            targets=() if frame.sequence == 0 else (target,),
            gesture=gestures[frame.sequence],
        )
        for frame in frames
    }

    clock = StepClock(start_ns=start_ns)
    actuator = VirtualActuator()
    pipeline = SynchronousPipeline(
        source=ReplayFrameSource(frames),
        backend=ScriptedInferenceBackend(perceptions),
        state_machine=DirectorStateMachine(started_at_ns=start_ns),
        controller=CompositionController(),
        actuator=actuator,
        clock_ns=clock,
    )

    for result in pipeline.run():
        pan, tilt = actuator.position
        print(
            json.dumps(
                {
                    "frame": result.frame.sequence,
                    "mode": result.decision.mode.value,
                    "gesture_edge": result.decision.gesture_edge.value,
                    "action": result.intent.action.value,
                    "pan": round(pan, 3),
                    "tilt": round(tilt, 3),
                    "total_ms": result.timings.total_ms,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
