"""A synchronous reference pipeline used before introducing concurrency."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from time import monotonic_ns

from .control import CompositionController
from .domain import PipelineResult, StageTimings
from .interfaces import Actuator, FrameSource, InferenceBackend
from .state_machine import DirectorStateMachine


class SynchronousPipeline:
    """Processes one frame at a time with explicit stage boundaries."""

    def __init__(
        self,
        *,
        source: FrameSource,
        backend: InferenceBackend,
        state_machine: DirectorStateMachine,
        controller: CompositionController,
        actuator: Actuator,
        clock_ns: Callable[[], int] = monotonic_ns,
    ) -> None:
        self._source = source
        self._backend = backend
        self._state_machine = state_machine
        self._controller = controller
        self._actuator = actuator
        self._clock_ns = clock_ns

    def step(self) -> PipelineResult | None:
        started_ns = self._clock_ns()
        frame = self._source.read()
        captured_ns = self._clock_ns()
        if frame is None:
            return None

        perception = self._backend.infer(frame)
        inferred_ns = self._clock_ns()
        if perception.frame_sequence != frame.sequence:
            raise ValueError("inference result does not match its input frame")

        decision = self._state_machine.update(perception, now_ns=inferred_ns)
        intent = self._controller.plan(perception, decision)
        decided_ns = self._clock_ns()

        self._actuator.apply(intent)
        finished_ns = self._clock_ns()
        timings = StageTimings(
            capture_ms=_to_ms(captured_ns - started_ns),
            inference_ms=_to_ms(inferred_ns - captured_ns),
            decision_ms=_to_ms(decided_ns - inferred_ns),
            actuation_ms=_to_ms(finished_ns - decided_ns),
            total_ms=_to_ms(finished_ns - started_ns),
            frame_age_ms=_to_ms(max(0, finished_ns - frame.captured_at_ns)),
        )
        return PipelineResult(
            frame=frame,
            perception=perception,
            decision=decision,
            intent=intent,
            timings=timings,
        )

    def run(self, *, limit: int | None = None) -> Iterator[PipelineResult]:
        if limit is not None and limit < 0:
            raise ValueError("pipeline limit must be non-negative")
        processed = 0
        while limit is None or processed < limit:
            result = self.step()
            if result is None:
                return
            yield result
            processed += 1


def _to_ms(duration_ns: int) -> float:
    return duration_ns / 1_000_000.0
