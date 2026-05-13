#!/usr/bin/env python3
# Copyright 2026 gxxl. MIT License.
"""Pure-Python fixed-rate IMU resampler for `/sync/imu`.

This helper keeps an independent raw-IMU buffer and emits at most one
resampled IMU point per poll. It is intentionally ROS-free so it can be
unit-tested without `rclpy`.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from fractions import Fraction
import threading


@dataclass(frozen=True)
class RawImuSample:
    """A source IMU sample in the steady-clock domain."""

    steady_ns: int
    frame_id: str
    lin_acc: tuple[float, float, float]
    ang_vel: tuple[float, float, float]


@dataclass(frozen=True)
class ResampledImuPoint:
    """A resampled IMU point on the fixed-rate output grid."""

    target_steady_ns: int
    frame_id: str
    lin_acc: tuple[float, float, float]
    ang_vel: tuple[float, float, float]


@dataclass(frozen=True)
class ResamplerOutcome:
    """Result of one polling step."""

    kind: str
    point: ResampledImuPoint | None = None
    target_steady_ns: int = 0
    gap_ns: int = 0
    source_kind: str = ''
    before_steady_ns: int = 0
    after_steady_ns: int = 0
    alpha: float = 0.0


class FixedRateImuResampler:
    """Maintain a fixed-rate IMU output grid over irregular raw samples."""

    def __init__(
        self,
        *,
        rate_hz: float,
        latency_ms: float,
        max_gap_ms: float,
        history_sec: float = 1.0,
        lag_jump_periods: int = 5,
    ) -> None:
        if rate_hz <= 0.0:
            raise ValueError('rate_hz must be positive')
        if latency_ms < 0.0:
            raise ValueError('latency_ms must be non-negative')
        if max_gap_ms <= 0.0:
            raise ValueError('max_gap_ms must be positive')
        if history_sec <= 0.0:
            raise ValueError('history_sec must be positive')

        rate = Fraction(str(rate_hz))
        period_ns = Fraction(1_000_000_000, 1) / rate

        self._period_num_ns = period_ns.numerator
        self._period_den = period_ns.denominator
        self.period_ns = self._period_num_ns / self._period_den

        self.latency_ns = int(round(latency_ms * 1e6))
        self.max_gap_ns = int(round(max_gap_ms * 1e6))
        self.history_ns = int(round(history_sec * 1e9))
        self._lag_jump_periods = lag_jump_periods
        self._trim_margin_ns = (
            2 * self._period_num_ns + self._period_den - 1
        ) // self._period_den

        self._buf: deque[RawImuSample] = deque()
        self._next_tick: int | None = None
        self._lock = threading.Lock()

    @property
    def buffer_depth(self) -> int:
        """Current raw-buffer depth."""
        with self._lock:
            return len(self._buf)

    def push_sample(
        self,
        *,
        steady_ns: int,
        frame_id: str,
        lin_acc: tuple[float, float, float],
        ang_vel: tuple[float, float, float],
    ) -> bool:
        """Append a new raw sample if it is strictly monotonic."""
        with self._lock:
            if steady_ns <= 0:
                return False

            if self._buf and steady_ns <= self._buf[-1].steady_ns:
                return False

            self._buf.append(
                RawImuSample(
                    steady_ns=steady_ns,
                    frame_id=frame_id,
                    lin_acc=lin_acc,
                    ang_vel=ang_vel,
                )
            )

            cutoff_ns = steady_ns - self.history_ns
            while len(self._buf) > 2 and self._buf[0].steady_ns < cutoff_ns:
                self._buf.popleft()

            return True

    def poll(self) -> ResamplerOutcome:
        """Emit at most one output point for the current safe window."""
        with self._lock:
            return self._poll_locked()

    def _poll_locked(self) -> ResamplerOutcome:
        """Emit at most one output point. Caller must hold ``_lock``."""
        if len(self._buf) < 2:
            return ResamplerOutcome(kind='wait')

        latest_ns = self._buf[-1].steady_ns
        safe_latest_ns = latest_ns - self.latency_ns
        if safe_latest_ns <= self._buf[0].steady_ns:
            return ResamplerOutcome(kind='wait')

        safe_tick = self._steady_ns_to_tick_floor(safe_latest_ns)
        if self._next_tick is None:
            self._next_tick = safe_tick

        if safe_tick - self._next_tick > self._lag_jump_periods:
            self._next_tick = safe_tick

        target_ns = self._tick_to_steady_ns(self._next_tick)
        if target_ns > safe_latest_ns:
            return ResamplerOutcome(kind='wait')

        exact = None
        for sample in self._buf:
            if sample.steady_ns == target_ns:
                exact = sample
                break
        if exact is not None:
            self._next_tick += 1
            self._trim_buffer(target_ns)
            return ResamplerOutcome(
                kind='publish',
                point=ResampledImuPoint(
                    target_steady_ns=target_ns,
                    frame_id=exact.frame_id,
                    lin_acc=exact.lin_acc,
                    ang_vel=exact.ang_vel,
                ),
                target_steady_ns=target_ns,
                source_kind='exact',
                before_steady_ns=exact.steady_ns,
                after_steady_ns=exact.steady_ns,
            )

        before = None
        after = None
        for i in range(len(self._buf) - 1):
            a = self._buf[i]
            b = self._buf[i + 1]
            if a.steady_ns <= target_ns <= b.steady_ns:
                before = a
                after = b
                break

        if before is None or after is None:
            if target_ns < self._buf[0].steady_ns:
                self._next_tick = self._steady_ns_to_tick_ceil(
                    self._buf[0].steady_ns)
            return ResamplerOutcome(kind='wait')

        gap_ns = after.steady_ns - before.steady_ns
        if gap_ns <= 0:
            return ResamplerOutcome(kind='wait')

        if gap_ns > self.max_gap_ns:
            self._next_tick += 1
            self._trim_buffer(target_ns)
            return ResamplerOutcome(
                kind='skip',
                target_steady_ns=target_ns,
                gap_ns=gap_ns,
                source_kind='skip_gap',
                before_steady_ns=before.steady_ns,
                after_steady_ns=after.steady_ns,
            )

        alpha = (target_ns - before.steady_ns) / gap_ns
        lin_acc = tuple(
            before.lin_acc[i] + alpha * (after.lin_acc[i] - before.lin_acc[i])
            for i in range(3)
        )
        ang_vel = tuple(
            before.ang_vel[i] + alpha * (after.ang_vel[i] - before.ang_vel[i])
            for i in range(3)
        )

        self._next_tick += 1
        self._trim_buffer(target_ns)

        return ResamplerOutcome(
            kind='publish',
            point=ResampledImuPoint(
                target_steady_ns=target_ns,
                frame_id=before.frame_id,
                lin_acc=lin_acc,
                ang_vel=ang_vel,
            ),
            target_steady_ns=target_ns,
            gap_ns=gap_ns,
            source_kind='interpolated',
            before_steady_ns=before.steady_ns,
            after_steady_ns=after.steady_ns,
            alpha=alpha,
        )

    def _trim_buffer(self, target_ns: int) -> None:
        trim_before_ns = target_ns - self._trim_margin_ns
        while len(self._buf) > 3 and self._buf[1].steady_ns < trim_before_ns:
            self._buf.popleft()

    def _steady_ns_to_tick_floor(self, steady_ns: int) -> int:
        return steady_ns * self._period_den // self._period_num_ns

    def _steady_ns_to_tick_ceil(self, steady_ns: int) -> int:
        tick = self._steady_ns_to_tick_floor(steady_ns)
        if self._tick_to_steady_ns(tick) < steady_ns:
            tick += 1
        return tick

    def _tick_to_steady_ns(self, tick: int) -> int:
        return tick * self._period_num_ns // self._period_den
