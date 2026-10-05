from __future__ import annotations

import unittest

from edge_ai_director.domain import Gesture, OperatingMode, Perception, TargetObservation
from edge_ai_director.state_machine import DirectorStateMachine, StateMachineConfig


SECOND = 1_000_000_000
TARGET = TargetObservation(
    center_x=0.5,
    center_y=0.33,
    area_ratio=0.2,
    confidence=0.9,
)


def perception(
    sequence: int,
    *,
    targets: tuple[TargetObservation, ...] = (TARGET,),
    gesture: Gesture = Gesture.NONE,
    showcase_pose: bool = False,
) -> Perception:
    return Perception(
        frame_sequence=sequence,
        completed_at_ns=sequence * SECOND,
        targets=targets,
        gesture=gesture,
        showcase_pose=showcase_pose,
    )


class DirectorStateMachineTests(unittest.TestCase):
    def test_held_lock_gesture_does_not_immediately_unlock(self) -> None:
        machine = DirectorStateMachine(started_at_ns=0)

        acquired = machine.update(perception(0), now_ns=0)
        locked = machine.update(
            perception(1, gesture=Gesture.LEFT_HAND_UP),
            now_ns=SECOND,
        )
        still_locked = machine.update(
            perception(2, gesture=Gesture.LEFT_HAND_UP),
            now_ns=2 * SECOND,
        )
        machine.update(perception(3), now_ns=3 * SECOND)
        unlocked = machine.update(
            perception(4, gesture=Gesture.LEFT_HAND_UP),
            now_ns=4 * SECOND,
        )

        self.assertEqual(acquired.mode, OperatingMode.TRACKING)
        self.assertEqual(locked.mode, OperatingMode.LOCKED)
        self.assertEqual(still_locked.mode, OperatingMode.LOCKED)
        self.assertEqual(still_locked.gesture_edge, Gesture.NONE)
        self.assertEqual(unlocked.mode, OperatingMode.TRACKING)

    def test_missing_target_progresses_from_search_to_privacy(self) -> None:
        machine = DirectorStateMachine(
            started_at_ns=0,
            config=StateMachineConfig(
                patrol_after_seconds=5,
                privacy_after_seconds=30,
            ),
        )

        searching = machine.update(perception(6, targets=()), now_ns=6 * SECOND)
        privacy = machine.update(perception(31, targets=()), now_ns=31 * SECOND)
        recovered = machine.update(perception(32), now_ns=32 * SECOND)

        self.assertEqual(searching.mode, OperatingMode.SEARCHING)
        self.assertEqual(privacy.mode, OperatingMode.PRIVACY)
        self.assertEqual(recovered.mode, OperatingMode.TRACKING)

    def test_showcase_requires_hold_time_and_exits_on_release(self) -> None:
        machine = DirectorStateMachine(
            started_at_ns=0,
            config=StateMachineConfig(showcase_hold_seconds=2.0),
        )

        waiting = machine.update(
            perception(0, showcase_pose=True),
            now_ns=0,
        )
        showcase = machine.update(
            perception(2, showcase_pose=True),
            now_ns=2 * SECOND,
        )
        released = machine.update(perception(3), now_ns=3 * SECOND)

        self.assertEqual(waiting.mode, OperatingMode.TRACKING)
        self.assertEqual(showcase.mode, OperatingMode.SHOWCASE)
        self.assertEqual(released.mode, OperatingMode.TRACKING)

    def test_reset_is_emitted_only_on_gesture_edge(self) -> None:
        machine = DirectorStateMachine(started_at_ns=0)

        first = machine.update(
            perception(0, gesture=Gesture.BOTH_HANDS_UP),
            now_ns=0,
        )
        held = machine.update(
            perception(1, gesture=Gesture.BOTH_HANDS_UP),
            now_ns=SECOND,
        )

        self.assertTrue(first.reset_requested)
        self.assertFalse(held.reset_requested)


if __name__ == "__main__":
    unittest.main()
