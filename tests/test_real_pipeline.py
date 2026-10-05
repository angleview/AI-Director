from __future__ import annotations

import unittest

from edge_ai_director.control import CompositionController
from edge_ai_director.domain import ControlAction, Gesture, OperatingMode
from edge_ai_director.pipeline import SynchronousPipeline
from edge_ai_director.replay import OpenCVVideoSource
from edge_ai_director.simulated import VirtualActuator
from edge_ai_director.state_machine import DirectorStateMachine
from edge_ai_director.ultralytics_backend import PoseBackendConfig, UltralyticsPoseBackend


class FakeArray:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def cpu(self) -> FakeArray:
        return self

    def numpy(self) -> FakeArray:
        return self

    def tolist(self) -> list[object]:
        return self._values


class FakeImage:
    shape = (360, 640, 3)


class FakeCapture:
    def __init__(self, frames: list[FakeImage]) -> None:
        self._frames = iter(frames)
        self.released = False

    def isOpened(self) -> bool:
        return True

    def read(self) -> tuple[bool, FakeImage | None]:
        frame = next(self._frames, None)
        return frame is not None, frame

    def release(self) -> None:
        self.released = True


class FakeCV2:
    def __init__(self, frames: list[FakeImage]) -> None:
        self.capture = FakeCapture(frames)

    def VideoCapture(self, _: str) -> FakeCapture:
        return self.capture


class FakeBoxes:
    def __init__(self, xywh: list[object], confidence: list[object]) -> None:
        self.xywh = FakeArray(xywh)
        self.conf = FakeArray(confidence)


class FakeKeypoints:
    def __init__(self, xy: list[object]) -> None:
        self.xy = FakeArray(xy)


class FakeResult:
    def __init__(self, boxes: FakeBoxes, keypoints: FakeKeypoints) -> None:
        self.boxes = boxes
        self.keypoints = keypoints


class FakeModel:
    def __init__(self, result: FakeResult) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

    def predict(self, **kwargs: object) -> list[FakeResult]:
        self.calls.append(kwargs)
        return [self._result]


def person_keypoints(
    *, nose: tuple[float, float], left_wrist: tuple[float, float], right_wrist: tuple[float, float]
) -> list[list[float]]:
    points = [[0.0, 0.0] for _ in range(17)]
    points[0] = [nose[0], nose[1]]
    points[1] = [nose[0] - 10.0, nose[1]]
    points[2] = [nose[0] + 10.0, nose[1]]
    points[9] = [left_wrist[0], left_wrist[1]]
    points[10] = [right_wrist[0], right_wrist[1]]
    return points


class StepClock:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> int:
        value = self.value
        self.value += 1_000_000
        return value


class RealAdapterPipelineTests(unittest.TestCase):
    def test_video_model_state_machine_and_virtual_actuator_share_one_pipeline(self) -> None:
        cv2 = FakeCV2([FakeImage()])
        keypoints = [
            person_keypoints(nose=(160, 180), left_wrist=(100, 280), right_wrist=(220, 280)),
            person_keypoints(nose=(480, 180), left_wrist=(420, 280), right_wrist=(540, 280)),
        ]
        model = FakeModel(
            FakeResult(
                FakeBoxes([[160, 180, 160, 180], [480, 180, 160, 180]], [0.9, 0.8]),
                FakeKeypoints(keypoints),
            )
        )
        source = OpenCVVideoSource("replay.mp4", cv2_module=cv2, clock_ns=lambda: 0)
        backend = UltralyticsPoseBackend(model=model, clock_ns=lambda: 2_000_000)
        actuator = VirtualActuator()
        pipeline = SynchronousPipeline(
            source=source,
            backend=backend,
            state_machine=DirectorStateMachine(started_at_ns=0),
            controller=CompositionController(),
            actuator=actuator,
            clock_ns=StepClock(),
        )

        results = list(pipeline.run())

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].decision.mode, OperatingMode.TRACKING)
        self.assertEqual(results[0].decision.target_count, 2)
        self.assertEqual(results[0].intent.action, ControlAction.HOLD)
        self.assertEqual(len(actuator.records), 1)
        self.assertEqual(len(model.calls), 1)
        self.assertTrue(cv2.capture.released)

    def test_pose_keypoints_generate_resolution_independent_gesture(self) -> None:
        keypoints = person_keypoints(
            nose=(320, 180), left_wrist=(250, 80), right_wrist=(390, 80)
        )
        model = FakeModel(
            FakeResult(FakeBoxes([[320, 180, 200, 240]], [0.95]), FakeKeypoints([keypoints]))
        )
        backend = UltralyticsPoseBackend(
            model=model,
            config=PoseBackendConfig(min_area_ratio=0.10),
            clock_ns=lambda: 10,
        )
        source = OpenCVVideoSource(
            "replay.mp4", cv2_module=FakeCV2([FakeImage()]), clock_ns=lambda: 5
        )

        perception = backend.infer(source.read())  # type: ignore[arg-type]

        self.assertEqual(perception.gesture, Gesture.BOTH_HANDS_UP)
        self.assertAlmostEqual(perception.targets[0].center_x, 0.5)
        self.assertAlmostEqual(perception.targets[0].area_ratio, 200 * 240 / (640 * 360))


if __name__ == "__main__":
    unittest.main()
