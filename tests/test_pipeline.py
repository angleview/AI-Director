from __future__ import annotations

import unittest

from edge_ai_director.control import CompositionController
from edge_ai_director.domain import (
    ControlAction,
    ControlIntent,
    Frame,
    Perception,
    TargetObservation,
)
from edge_ai_director.pipeline import SynchronousPipeline
from edge_ai_director.simulated import ReplayFrameSource, ScriptedInferenceBackend, VirtualActuator
from edge_ai_director.state_machine import DirectorStateMachine


class StepClock:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> int:
        value = self.value
        self.value += 1_000_000
        return value


class SynchronousPipelineTests(unittest.TestCase):
    def test_one_input_produces_one_ordered_actuation_record(self) -> None:
        frames = (
            Frame(sequence=0, captured_at_ns=0, width=640, height=360),
            Frame(sequence=1, captured_at_ns=0, width=640, height=360),
        )
        target = TargetObservation(
            center_x=0.8,
            center_y=0.6,
            area_ratio=0.2,
            confidence=0.9,
        )
        perceptions = {
            frame.sequence: Perception(
                frame_sequence=frame.sequence,
                completed_at_ns=0,
                targets=(target,),
            )
            for frame in frames
        }
        actuator = VirtualActuator()
        pipeline = SynchronousPipeline(
            source=ReplayFrameSource(frames),
            backend=ScriptedInferenceBackend(perceptions),
            state_machine=DirectorStateMachine(started_at_ns=0),
            controller=CompositionController(),
            actuator=actuator,
            clock_ns=StepClock(),
        )

        results = list(pipeline.run())

        self.assertEqual([result.frame.sequence for result in results], [0, 1])
        self.assertEqual([record.frame_sequence for record in actuator.records], [0, 1])
        self.assertTrue(
            all(result.intent.action is ControlAction.RELATIVE_MOVE for result in results)
        )
        self.assertTrue(all(result.timings.total_ms == 4.0 for result in results))

    def test_virtual_actuator_clips_motion_to_safety_limits(self) -> None:
        actuator = VirtualActuator(
            pan_limits=(-1.0, 1.0),
            tilt_limits=(-1.0, 1.0),
            reset_tilt=0.0,
        )
        actuator.apply(
            ControlIntent(
                frame_sequence=0,
                action=ControlAction.RELATIVE_MOVE,
                pan_delta_degrees=5.0,
                tilt_delta_degrees=-5.0,
            )
        )

        self.assertEqual(actuator.position, (1.0, -1.0))
        self.assertTrue(actuator.records[0].clipped)


if __name__ == "__main__":
    unittest.main()
