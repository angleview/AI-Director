"""Learning exercises: stdlib only; no network, camera, model inference or physical motion.

Run from any directory:
    python path/to/practice.py all
The source and evidence files are resolved relative to this script.
Assertions deliberately check the current repository's known learning examples.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT / "src"))

from edge_ai_director.benchmark import summarize
from edge_ai_director.control import CompositionController
from edge_ai_director.domain import (
    ControlAction, ControlIntent, Decision, Frame, Gesture,
    OperatingMode, Perception, TargetObservation,
)
from edge_ai_director.pipeline import SynchronousPipeline
from edge_ai_director.simulated import ReplayFrameSource, VirtualActuator
from edge_ai_director.state_machine import DirectorStateMachine


def normalise(value: float, dimension: int) -> float:
    if dimension <= 0:
        raise ValueError("dimension must be positive")
    return max(0.0, min(1.0, value / dimension))


def gesture_edges(values: list[str]) -> list[tuple[int, str]]:
    """Match the project's non-NONE gesture-type-change rule."""
    previous = "NONE"
    result = []
    for index, value in enumerate(values):
        if value != "NONE" and value != previous:
            result.append((index, value))
        previous = value
    return result


def sample_percentile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("empty samples")
    if not 0 <= q <= 1:
        raise ValueError("q must be in [0, 1]")
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower, upper = math.floor(position), math.ceil(position)
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def two_sum(values: list[int], target: int) -> tuple[int, int] | None:
    seen: dict[int, int] = {}
    for index, value in enumerate(values):
        needed = target - value
        if needed in seen:
            return seen[needed], index
        seen[value] = index
    return None


def python_basics() -> None:
    a = [1, 2]
    b = a
    b.append(3)
    copied = a.copy()
    copied.append(4)
    assert a == [1, 2, 3] and copied == [1, 2, 3, 4]

    @dataclass(frozen=True)
    class Box:
        payload: list[int]

    box = Box([1])
    box.payload.append(2)
    assert box.payload == [1, 2]  # Frozen fields do not freeze nested data.
    assert normalise(480, 640) == 0.75
    assert normalise(-1, 640) == 0
    assert normalise(900, 640) == 1
    try:
        normalise(1, 0)
    except ValueError:
        pass
    else:
        raise AssertionError("zero dimension must be rejected")

    iterator = (index for index in range(3))
    assert next(iterator) == 0
    assert list(iterator) == [1, 2]
    print("python: reference/copy, frozen payload, normalisation, generator OK")


def observation(
    sequence: int, *, gesture: Gesture = Gesture.NONE,
    targets: tuple[TargetObservation, ...] | None = None,
    showcase: bool = False,
) -> Perception:
    if targets is None:
        targets = (TargetObservation(0.8, 0.6, 0.2, 0.9),)
    return Perception(
        frame_sequence=sequence,
        completed_at_ns=sequence * 1_000_000_000,
        targets=targets, gesture=gesture, showcase_pose=showcase,
    )


def core_examples() -> None:
    controller = CompositionController()
    decision = Decision(OperatingMode.TRACKING, 1)
    intent = controller.plan(observation(0), decision)
    assert intent.action is ControlAction.RELATIVE_MOVE
    assert math.isclose(intent.pan_delta_degrees, 4)
    assert math.isclose(intent.tilt_delta_degrees, 3.24)
    actuator = VirtualActuator()
    actuator.apply(intent)
    assert math.isclose(actuator.position[0], 4)
    assert math.isclose(actuator.position[1], -86.76)
    print(f"control: delta=(4.00, 3.24), virtual position={actuator.position}")

    central = observation(1, targets=(TargetObservation(0.51, 0.34, 0.2, 0.9),))
    assert controller.plan(central, decision).action is ControlAction.HOLD
    actuator.apply(ControlIntent(2, ControlAction.RELATIVE_MOVE, 200, -200))
    assert actuator.position == (90, -90)
    assert actuator.records[-1].clipped

    machine = DirectorStateMachine(started_at_ns=0)
    gestures = [Gesture.NONE, Gesture.LEFT_HAND_UP, Gesture.LEFT_HAND_UP,
                Gesture.NONE, Gesture.LEFT_HAND_UP, Gesture.BOTH_HANDS_UP]
    modes = []
    edges = []
    for sequence, gesture in enumerate(gestures):
        result = machine.update(observation(sequence, gesture=gesture),
                                now_ns=sequence * 1_000_000_000)
        modes.append(result.mode.value)
        edges.append(result.gesture_edge.value)
    assert modes == ["TRACKING", "LOCKED", "LOCKED", "LOCKED", "TRACKING", "TRACKING"]
    assert edges == ["NONE", "LEFT_HAND_UP", "NONE", "NONE",
                     "LEFT_HAND_UP", "BOTH_HANDS_UP"]
    print("state modes:", modes)
    print("gesture events:", edges)

    timeout = DirectorStateMachine(started_at_ns=0)
    assert (
        timeout.update(observation(0, targets=()), now_ns=6_000_000_000).mode
        is OperatingMode.SEARCHING
    )
    assert (
        timeout.update(observation(1, targets=()), now_ns=31_000_000_000).mode
        is OperatingMode.PRIVACY
    )
    assert (
        timeout.update(observation(2), now_ns=32_000_000_000).mode
        is OperatingMode.TRACKING
    )

    showcase_machine = DirectorStateMachine(started_at_ns=0)
    assert (
        showcase_machine.update(observation(0, showcase=True), now_ns=0).mode
        is OperatingMode.TRACKING
    )
    assert showcase_machine.update(observation(1, showcase=True),
                                   now_ns=2_000_000_000).mode is OperatingMode.SHOWCASE
    assert showcase_machine.update(observation(2),
                                   now_ns=3_000_000_000).mode is OperatingMode.TRACKING

    class WrongFrameBackend:
        def infer(self, frame: Frame) -> Perception:
            return observation(frame.sequence + 1)

    guarded_actuator = VirtualActuator()
    pipeline = SynchronousPipeline(
        source=ReplayFrameSource([Frame(0, 0, 640, 360)]),
        backend=WrongFrameBackend(),
        state_machine=DirectorStateMachine(started_at_ns=0),
        controller=controller, actuator=guarded_actuator, clock_ns=lambda: 0,
    )
    try:
        pipeline.step()
    except ValueError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("mismatched frame must be rejected")
    assert not guarded_actuator.records
    print("core: dead zone, absolute limits, timeout, showcase, wrong-frame guard OK")


def evidence_examples() -> None:
    reports = {}
    for size in (640, 480):
        path = PROJECT / f"artifacts/benchmarks/pi5-yolov8n-pose-ncnn-bus-img{size}.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        assert report["configuration"]["imgsz"] == size
        rows = report["measurements"]
        assert len(rows) == report["configuration"]["measured_runs"] == 30
        for field in ("decode_ms", "inference_ms", "postprocess_ms", "end_to_end_ms"):
            recalculated = summarize([row[field] for row in rows])
            for key in ("p50", "p95"):
                assert math.isclose(recalculated[key], report["summary_ms"][field][key],
                                    rel_tol=1e-10, abs_tol=1e-8)
        summary = report["summary_ms"]
        print(f"{size}: inference p50/p95="
              f"{summary['inference_ms']['p50']:.2f}/{summary['inference_ms']['p95']:.2f} ms; "
              f"end-to-end="
              f"{summary['end_to_end_ms']['p50']:.2f}/{summary['end_to_end_ms']['p95']:.2f} ms; "
              f"detections={sorted({row['detections'] for row in rows})}")
        reports[size] = report
    assert (
        reports[640]["artifacts"]["input"]["sha256"]
        == reports[480]["artifacts"]["input"]["sha256"]
    )
    model_hashes = lambda report: sorted(
        (file["name"], file["sha256"]) for file in report["artifacts"]["model"]["files"]
    )
    assert model_hashes(reports[640]) == model_hashes(reports[480])
    assert {row["detections"] for row in reports[640]["measurements"]} == {4}
    assert {row["detections"] for row in reports[480]["measurements"]} == {300}
    slowdown = (reports[480]["summary_ms"]["end_to_end_ms"]["p50"] /
                reports[640]["summary_ms"]["end_to_end_ms"]["p50"])
    print(f"480/640 end-to-end median ratio: {slowdown:.2f}x")

    path = PROJECT / "artifacts/replays/pi5-bus-static-img640.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    frames = [row for row in records if row["type"] == "frame"]
    summary = next(row for row in records if row["type"] == "summary")
    assert [row["sequence"] for row in frames] == list(range(30))
    assert summary["processed_frames"] == len(frames) == 30
    assert {row["target_count"] for row in frames} == {2}
    assert Counter(row["mode"] for row in frames) == {"TRACKING": 22, "SHOWCASE": 8}
    recomputed = summarize([row["timings_ms"]["total"] for row in frames])
    for key in ("p50", "p95"):
        assert math.isclose(recomputed[key], summary["pipeline_total_ms"][key],
                            rel_tol=1e-10, abs_tol=1e-8)
    print(f"saved replay: 30 ordered frames; modes={dict(Counter(row['mode'] for row in frames))}; "
          f"pipeline p50/p95={recomputed['p50']:.2f}/{recomputed['p95']:.2f} ms")
    print("evidence: saved reports checked; no new model inference was performed")


def exercise_answers() -> None:
    assert (
        gesture_edges(["NONE", "LEFT", "LEFT", "NONE", "LEFT", "BOTH"])
        == [(1, "LEFT"), (4, "LEFT"), (5, "BOTH")]
    )
    assert gesture_edges([]) == []
    assert sample_percentile([100, 10, 40, 20, 30], 0.5) == 30
    assert math.isclose(sample_percentile([100, 10, 40, 20, 30], 0.95), 88)
    assert sample_percentile([7], 0.95) == 7
    for values, q in (([], 0.5), ([1], -0.1), ([1], 1.1)):
        try:
            sample_percentile(values, q)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid percentile input must be rejected")
    assert two_sum([2, 7, 11, 15], 9) == (0, 1)
    assert two_sum([3, 3], 6) == (0, 1)
    assert two_sum([], 1) is None
    assert two_sum([1], 2) is None
    assert two_sum([-2, 5, 7], 3) == (0, 1)
    print("answers: gesture edges, percentile, two-sum boundary examples OK")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chapter", choices=["python", "core", "evidence", "exercises", "all"])
    chapter = parser.parse_args().chapter
    actions = {"python": python_basics, "core": core_examples,
               "evidence": evidence_examples, "exercises": exercise_answers}
    for name, action in actions.items():
        if chapter in (name, "all"):
            action()
    print("Selected learning checks passed.")


if __name__ == "__main__":
    main()
