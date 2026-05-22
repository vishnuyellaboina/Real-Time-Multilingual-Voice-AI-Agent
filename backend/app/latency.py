from __future__ import annotations

from time import perf_counter

from .models import LatencyBreakdown


class LatencyTracker:
    def __init__(self) -> None:
        self.started = perf_counter()
        self.dispatch = self.started
        self.reasoning_done = self.started
        self.tools_done = self.started
        self.render_done = self.started

    def mark_dispatch(self) -> None:
        self.dispatch = perf_counter()

    def mark_reasoning_done(self) -> None:
        self.reasoning_done = perf_counter()

    def mark_tools_done(self) -> None:
        self.tools_done = perf_counter()

    def mark_render_done(self) -> None:
        self.render_done = perf_counter()

    def build(self) -> LatencyBreakdown:
        return LatencyBreakdown(
            speech_end_to_dispatch_ms=round((self.dispatch - self.started) * 1000, 2),
            reasoning_ms=round((self.reasoning_done - self.dispatch) * 1000, 2),
            tool_ms=round((self.tools_done - self.reasoning_done) * 1000, 2),
            response_render_ms=round((self.render_done - self.tools_done) * 1000, 2),
            total_ms=round((self.render_done - self.started) * 1000, 2),
        )

