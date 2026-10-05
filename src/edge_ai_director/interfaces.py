"""Ports implemented by real hardware, replay sources, and test doubles."""

from __future__ import annotations

from typing import Protocol

from .domain import ControlIntent, Frame, Perception


class FrameSource(Protocol):
    def read(self) -> Frame | None:
        """Return the next frame or ``None`` when the source is exhausted."""


class InferenceBackend(Protocol):
    def infer(self, frame: Frame) -> Perception:
        """Produce observations for the supplied frame."""


class Actuator(Protocol):
    def apply(self, intent: ControlIntent) -> None:
        """Apply or record one ordered control intent."""
