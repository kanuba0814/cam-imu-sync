#!/usr/bin/env python3
# Copyright 2026 gxxl. MIT License.
"""Pure-Python synchronisation state machine for cam_imu_sync.

This module implements the core sync algorithm with a three-phase
state machine:

1. **WAIT_IMU_READY** – wait for IMU pipeline to stabilise
   (and optionally for external ``pipeline_ready`` signal).
2. **WAIT_FIRST_SYNC** – wait for IMU coverage to reach the first
   camera frame's target timestamp **in the steady-clock domain**.
3. **READY** – normal synchronisation with health monitoring
   and automatic re-arm on consecutive failures.

**Steady-domain principle** – All synchronisation decisions (target
alignment, interval construction, interpolation, failure detection)
use ``time.monotonic_ns()`` / ``time.monotonic()`` timestamps.
``header.stamp`` is retained only for observation / ROS output.

**No ROS dependency** – all interactions with the middleware go through
the ``sync_node`` wrapper.  This makes the logic fully testable with
plain ``pytest``.
"""

from __future__ import annotations

import collections
import copy
import math
import threading
import time as _time
from typing import Any, Callable, NamedTuple, Optional

from .models import (
    FrameSample, ImuPipelineStatus, ImuRawSample,
    SyncConfig, SyncState, SyncStats,
)


# ── public result types ──────────────────────────────────────────────

class SyncBatch(NamedTuple):
    """Output of a successful ``try_sync`` call."""

    imu_msgs: list[Any]
    """Ordered IMU messages in (prev_aligned_steady, target_steady],
    with an optional interpolated boundary point appended."""

    image_msg: Any
    """The camera message, **not yet re-stamped** (caller must stamp)."""

    t_aligned: float
    """Header-domain aligned timestamp (for ROS output stamping)."""

    t_aligned_steady: float
    """Steady-domain aligned timestamp that drove the sync decision."""

    # ── diagnostic fields (defaults for backward compat) ─────────
    cam_frame_id: int = 0
    """Sequential camera frame ID."""

    cam_header_ns: int = 0
    """Original camera header timestamp in nanoseconds."""

    cam_steady_ns: int = 0
    """``time.monotonic_ns()`` when camera frame was enqueued."""

    imu_ids: tuple = ()
    """Sequential IMU IDs for each sample in the batch."""

    imu_steady_ns_list: tuple = ()
    """``time.monotonic_ns()`` for each IMU sample in the batch."""

    interp_used: bool = False
    """Whether boundary interpolation was applied."""


class LogEntry(NamedTuple):
    """A pending log message emitted by the manager."""

    level: str          # 'info', 'warn', 'error'
    message: str


# ── utilities ────────────────────────────────────────────────────────

def stamp2sec(stamp) -> float:
    """Convert ``builtin_interfaces/Time`` to seconds."""
    return stamp.sec + stamp.nanosec * 1e-9


def sec2stamp(t: float):
    """Convert seconds to ``builtin_interfaces/Time``-compatible dict.

    Returns a ``(sec, nanosec)`` tuple – the caller constructs the ROS
    message to keep this module ROS-free.
    """
    sec = int(t)
    nsec = int(round((t - sec) * 1e9))
    if nsec >= 1_000_000_000:
        sec += 1
        nsec -= 1_000_000_000
    return sec, nsec


def lerp_imu_steady(
    imu_a, imu_b,
    t0_steady: float, t1_steady: float, t_target_steady: float,
    *, make_imu: Callable,
):
    """Linearly interpolate two IMU messages using **steady-domain** time.

    Parameters
    ----------
    imu_a, imu_b : sensor_msgs/Imu (or duck-typed equivalent)
    t0_steady, t1_steady : float
        Steady-clock timestamps (seconds) of imu_a and imu_b.
    t_target_steady : float
        The steady-domain target to interpolate at.
    make_imu : callable
        Factory that constructs an Imu message.

    Returns
    -------
    Imu-like object with header stamp set from the *header-domain*
    interpolation (for downstream ROS compat) but the *decision* was
    made in steady domain.
    """
    dt = t1_steady - t0_steady
    if abs(dt) < 1e-9:
        out = copy.deepcopy(imu_a)
        return out

    alpha = max(0.0, min(1.0, (t_target_steady - t0_steady) / dt))
    beta = 1.0 - alpha

    la = imu_a.linear_acceleration
    lb = imu_b.linear_acceleration
    wa = imu_a.angular_velocity
    wb = imu_b.angular_velocity

    # For the output header stamp, interpolate header-domain as well
    # (best-effort for downstream consumers).
    h0 = stamp2sec(imu_a.header.stamp)
    h1 = stamp2sec(imu_b.header.stamp)
    h_target = h0 + alpha * (h1 - h0)
    s, ns = sec2stamp(h_target)

    return make_imu(
        sec=s,
        nanosec=ns,
        frame_id=imu_a.header.frame_id,
        lin_acc=(beta * la.x + alpha * lb.x,
                 beta * la.y + alpha * lb.y,
                 beta * la.z + alpha * lb.z),
        ang_vel=(beta * wa.x + alpha * wb.x,
                 beta * wa.y + alpha * wb.y,
                 beta * wa.z + alpha * wb.z),
    )


# Keep legacy lerp_imu for backward compatibility (tests etc.)
def lerp_imu(imu_a, imu_b, t_target: float, *, make_imu: Callable):
    """Linearly interpolate via header timestamps (legacy)."""
    t0 = stamp2sec(imu_a.header.stamp)
    t1 = stamp2sec(imu_b.header.stamp)
    dt = t1 - t0
    if abs(dt) < 1e-9:
        out = copy.deepcopy(imu_a)
        s, ns = sec2stamp(t_target)
        out.header.stamp.sec = s
        out.header.stamp.nanosec = ns
        return out

    alpha = max(0.0, min(1.0, (t_target - t0) / dt))
    beta = 1.0 - alpha

    la = imu_a.linear_acceleration
    lb = imu_b.linear_acceleration
    wa = imu_a.angular_velocity
    wb = imu_b.angular_velocity

    s, ns = sec2stamp(t_target)
    return make_imu(
        sec=s,
        nanosec=ns,
        frame_id=imu_a.header.frame_id,
        lin_acc=(beta * la.x + alpha * lb.x,
                 beta * la.y + alpha * lb.y,
                 beta * la.z + alpha * lb.z),
        ang_vel=(beta * wa.x + alpha * wb.x,
                 beta * wa.y + alpha * wb.y,
                 beta * wa.z + alpha * wb.z),
    )


# ── Welford online stats (local, for IMU period tracking) ───────────

class _OnlineStats:
    """Single-pass running mean and standard deviation (Welford)."""

    __slots__ = ('n', '_mean', '_m2')

    def __init__(self) -> None:
        self.n = 0
        self._mean = 0.0
        self._m2 = 0.0

    def update(self, x: float) -> None:
        self.n += 1
        d1 = x - self._mean
        self._mean += d1 / self.n
        d2 = x - self._mean
        self._m2 += d1 * d2

    @property
    def mean(self) -> float:
        return self._mean if self.n > 0 else 0.0

    @property
    def std(self) -> float:
        return math.sqrt(self._m2 / (self.n - 1)) if self.n >= 2 else 0.0

    def reset(self) -> None:
        self.n = 0
        self._mean = 0.0
        self._m2 = 0.0


# ── core state machine ──────────────────────────────────────────────

class SyncManager:
    """Thread-safe synchronisation state machine.

    Implements a three-phase startup protocol:

    1. ``WAIT_IMU_READY`` — collect IMU samples, wait for pipeline to
       stabilise (and optionally for external ``pipeline_ready`` flag).
    2. ``WAIT_FIRST_SYNC`` — wait for first camera frame whose
       ``target_steady`` is fully covered by IMU buffer (steady domain).
    3. ``READY`` — normal synchronisation with health monitoring.

    **All sync decisions use the steady (monotonic) clock domain.**
    Header-domain timestamps are preserved only for ROS output and
    diagnostic observation.

    The two input methods (:meth:`on_imu`, :meth:`on_image`) and the
    output method (:meth:`try_sync`) each acquire only the lock they
    need (``_imu_lock`` or ``_img_lock``).  The snapshot extraction in
    ``try_sync`` acquires both locks briefly, then releases them before
    performing interpolation / building the output batch.
    """

    def __init__(
        self,
        cfg: SyncConfig,
        *,
        make_imu: Callable,
        clock: Callable[[], float] = _time.monotonic,
    ) -> None:
        self.cfg = cfg
        self._make_imu = make_imu
        self._clock = clock

        # ── IMU state (guarded by _imu_lock) ─────────────────────────
        # Buffer entries: (t_header_sec, msg, imu_id, steady_ns)
        # Primary key for sync: steady_ns (4th element)
        self._imu_lock = threading.Lock()
        self._imu_buf: collections.deque = collections.deque()
        self._last_imu_t: float = 0.0      # header timestamp monotonicity
        self._last_imu_mono: float = 0.0   # wall-clock of last IMU
        self._next_imu_id: int = 1         # auto-increment counter
        self._latest_imu_steady_sec: float = 0.0   # latest IMU steady time

        # ── Image state (guarded by _img_lock) ───────────────────────
        self._img_lock = threading.Lock()
        self._img_queue: collections.deque[FrameSample] = collections.deque()
        self._last_img_t: float = 0.0      # header timestamp monotonicity
        self._next_cam_frame_id: int = 1   # auto-increment counter

        # ── Shared sync state ────────────────────────────────────────
        # STEADY domain — the ONLY prev-aligned used for interval
        self._prev_aligned_steady_t: float = 0.0

        # ── deferred cross-lock reset flag ────────────────────────────
        self._deferred_imu_reset: bool = False
        self._deferred_img_reset: bool = False

        # ── three-phase state machine ────────────────────────────────
        self._state: SyncState = SyncState.WAIT_IMU_READY
        self._first_sync_done: bool = False
        self._consecutive_fail_count: int = 0
        self._startup_mono: float = clock()  # monotonic time at init

        # ── WAIT_FIRST_SYNC tracking ─────────────────────────────────
        self._first_sync_wait_start: float = 0.0
        self._first_sync_drop_count: int = 0

        # ── IMU pipeline readiness tracking ──────────────────────────
        self._imu_period_tracker = _OnlineStats()
        self._imu_period_ring: collections.deque = collections.deque(
            maxlen=80)
        self._last_imu_steady_for_period: int = 0

        # External pipeline_ready flag (set by sync_node from topic)
        self._external_imu_ready: bool = False

        # ── diagnostics ──────────────────────────────────────────────
        self.stats = SyncStats()
        self._pending_logs: list[LogEntry] = []

        # ── Phase 1A: unified time domain ─────────────────────────────
        # ros_minus_steady_offset: the SINGLE offset that maps
        # steady_clock ns → ROS time.  Captured once at startup,
        # held constant for the entire run.
        # Formula: ros_stamp_sec = steady_ns / 1e9 + offset
        self._ros_minus_steady_offset: float = 0.0
        self._offset_initialized: bool = False

        # ── Phase 1A: deterministic mode flag ─────────────────────────
        self._deterministic_sync: bool = cfg.deterministic_sync

        # ── Phase 1A: tid tracking (packet-loss / ordering) ──────────
        self._last_tid: int = 0
        self._tid_gap_count: int = 0
        self._tid_reorder_count: int = 0

        # ── Phase 1A: camera stability tracking ──────────────────────
        self._cam_period_ring: collections.deque = collections.deque(
            maxlen=max(cfg.min_stable_cam_frames + 5, 20))
        self._last_cam_steady_for_period: int = 0
    # ── public read-only properties ───────────────────────────────

    @property
    def imu_buf_depth(self) -> int:
        """Current number of IMU samples in the buffer (lock-free)."""
        return len(self._imu_buf)

    @property
    def img_queue_depth(self) -> int:
        """Current number of images in the queue (lock-free)."""
        return len(self._img_queue)

    @property
    def state(self) -> SyncState:
        """Current state machine phase."""
        return self._state

    # ── external IMU ready flag (set by sync_node) ───────────────

    def set_external_imu_ready(self, ready: bool) -> None:
        """Called by the ROS layer when ``/imu/pipeline_ready`` is received."""
        self._external_imu_ready = ready

    # ── internal helpers ─────────────────────────────────────────────

    def _log(self, level: str, msg: str) -> None:
        """Queue a log message for the ROS layer to emit."""
        self._pending_logs.append(LogEntry(level, msg))

    def drain_logs(self) -> list[LogEntry]:
        """Return and clear pending log entries (called by sync_node)."""
        logs = self._pending_logs
        self._pending_logs = []
        return logs

    # ── Phase 1A: unified time domain ────────────────────────────────

    def init_time_offset(self, ros_now_ns: int, steady_now_ns: int) -> None:
        """Capture the one-shot ROS-minus-steady offset.

        Called once at sync node startup.  The offset is held constant
        for the entire run.

        Parameters
        ----------
        ros_now_ns : int
            ``rclpy.clock.Clock().now().nanoseconds`` at call time.
        steady_now_ns : int
            ``time.monotonic_ns()`` at call time.
        """
        if self._offset_initialized:
            return
        self._ros_minus_steady_offset = (ros_now_ns - steady_now_ns) / 1e9
        self._offset_initialized = True
        self._log('info',
                  f'[Phase 1A] offset captured: '
                  f'ros_minus_steady = {self._ros_minus_steady_offset:.6f} s')

    @property
    def ros_minus_steady_offset(self) -> float:
        """The one-shot offset mapping steady→ROS time."""
        return self._ros_minus_steady_offset

    @property
    def offset_initialized(self) -> bool:
        """Whether the time offset has been captured."""
        return self._offset_initialized

    def steady_ns_to_ros_sec(self, steady_ns: int) -> float:
        """Map a steady_clock nanosecond value to ROS-time seconds.

        This is the SINGLE mapping function used for ALL output
        header.stamp values in Phase 1A deterministic mode.
        """
        return steady_ns / 1e9 + self._ros_minus_steady_offset

    def on_imu_raw(self, raw: ImuRawSample,
                   now_mono: float | None = None,
                   ) -> int:
        """Enqueue an IMU sample from ImuRawHw (Phase 1A).

        Uses ``raw.rx_steady_ns`` as the primary sync time.
        ``tid`` is tracked for packet-loss / ordering diagnostics only.

        Parameters
        ----------
        raw : ImuRawSample
            Extracted data from the ImuRawHw message.
        now_mono : float, optional
            ``time.monotonic()`` (injected for testing).

        Returns
        -------
        int
            Assigned ``imu_id`` (>0) on success, 0 if rejected.
        """
        if now_mono is None:
            now_mono = self._clock()

        steady_ns = raw.rx_steady_ns
        # Use steady ns as the canonical "header" time in seconds
        # for buffer management (replaces header timestamp role)
        t_steady_sec = steady_ns / 1e9

        # tid-based packet-loss / ordering check
        self._check_tid(raw.tid)

        with self._imu_lock:
            # Apply any deferred reset
            if self._deferred_imu_reset:
                self._reset_imu_unlocked()
                self._deferred_imu_reset = False

            # Monotonicity check on steady time
            if self._last_imu_t > 0.0 and t_steady_sec <= self._last_imu_t:
                # Allow tiny jitter (< 0.1 ms) — can happen with
                # timer-based polling
                delta = t_steady_sec - self._last_imu_t
                if abs(delta) > 0.001:
                    self.stats.timestamp_anomaly_count += 1
                    self._log('warn',
                              f'IMU steady regression {delta*1e3:.2f} ms')
                return 0

            imu_id = self._next_imu_id
            self._next_imu_id += 1

            self._last_imu_t = t_steady_sec
            self._last_imu_mono = now_mono

            # Build a synthetic Imu message for the batch output
            # (will be re-stamped by sync_node before publishing)
            synth_msg = self._make_imu(
                sec=0, nanosec=0,  # placeholder; rewritten on output
                frame_id=raw.frame_id,
                lin_acc=raw.lin_acc,
                ang_vel=raw.ang_vel,
            )

            self._imu_buf.append((t_steady_sec, synth_msg, imu_id, steady_ns))

            # Update latest steady time
            if steady_ns > 0:
                steady_sec = steady_ns / 1e9
                if steady_sec > self._latest_imu_steady_sec:
                    self._latest_imu_steady_sec = steady_sec

            # Trim stale data
            cutoff = t_steady_sec - self.cfg.imu_buffer_sec
            while self._imu_buf and self._imu_buf[0][0] < cutoff:
                self._imu_buf.popleft()

        # Update period tracker
        self._update_imu_period_tracker(steady_ns)

        # Store assigned id back on the sample for diagnostics
        raw.imu_id = imu_id

        return imu_id

    def _check_tid(self, tid: int) -> None:
        """Track tid continuity for packet-loss/ordering diagnostics.

        tid wraps at ~60000.  Gap/reorder detected by comparing with
        the previous value.
        """
        if self._last_tid == 0:
            self._last_tid = tid
            return

        expected = self._last_tid + 1
        if expected > 60000:
            expected = 1

        if tid != expected:
            delta = tid - self._last_tid
            if delta < 0:
                delta += 60000
            if delta > 30000:
                # Probable reorder (delta > half range)
                self._tid_reorder_count += 1
                self._log('warn',
                          f'tid reorder: prev={self._last_tid} cur={tid}')
            elif delta > 1:
                self._tid_gap_count += 1
                # Only log occasionally to avoid spam
                if self._tid_gap_count <= 10 or self._tid_gap_count % 100 == 0:
                    self._log('warn',
                              f'tid gap: prev={self._last_tid} cur={tid} '
                              f'(missed {delta - 1}, total_gaps='
                              f'{self._tid_gap_count})')
        self._last_tid = tid

    # ── Phase 1A: camera stability tracking ──────────────────────────

    def _update_cam_period_tracker(self, steady_ns: int) -> None:
        """Track inter-arrival period of camera frames (steady domain)."""
        if self._last_cam_steady_for_period > 0 and steady_ns > 0:
            period_ms = (steady_ns - self._last_cam_steady_for_period) / 1e6
            if 0 < period_ms < 200:  # sanity
                self._cam_period_ring.append(period_ms)
        if steady_ns > 0:
            self._last_cam_steady_for_period = steady_ns

    def _check_cam_stable(self) -> bool:
        """Check whether camera inter-arrival is stable enough."""
        ring = self._cam_period_ring
        n = len(ring)
        if n < self.cfg.min_stable_cam_frames:
            return False
        mean_p = sum(ring) / n
        var_p = sum((x - mean_p) ** 2 for x in ring) / (n - 1)
        std_p = math.sqrt(var_p) if var_p > 0 else 0.0
        return std_p <= self.cfg.cam_stable_max_std_ms

    # ── internal unlocked reset helpers ────────────────────────────────

    def _reset_imu_unlocked(self) -> None:
        """Clear IMU state.  Caller MUST hold ``_imu_lock``."""
        self._imu_buf.clear()
        self._last_imu_t = 0.0
        self._latest_imu_steady_sec = 0.0

    def _reset_img_unlocked(self) -> None:
        """Clear image state.  Caller MUST hold ``_img_lock``."""
        self._img_queue.clear()
        self._last_img_t = 0.0

    def _apply_deferred_resets(self) -> None:
        """Apply any deferred cross-lock resets.  Called by try_sync."""
        if self._deferred_img_reset:
            with self._img_lock:
                self._reset_img_unlocked()
            self._deferred_img_reset = False
        if self._deferred_imu_reset:
            with self._imu_lock:
                self._reset_imu_unlocked()
            self._deferred_imu_reset = False

    # ── state transition helper ──────────────────────────────────────

    def _transition_to(self, new_state: SyncState) -> None:
        """Log and record a state machine transition."""
        old = self._state
        self._state = new_state
        self.stats.state_transitions += 1
        self._log('info',
                  f'State: {old.value} → {new_state.value}')

    # ── IMU pipeline readiness (local estimate) ──────────────────────

    def _update_imu_period_tracker(self, steady_ns: int) -> None:
        """Track inter-arrival period of IMU samples."""
        if self._last_imu_steady_for_period > 0 and steady_ns > 0:
            period_ms = (steady_ns - self._last_imu_steady_for_period) / 1e6
            if 0 < period_ms < 100:  # sanity: discard obvious outliers
                self._imu_period_ring.append(period_ms)
                self._imu_period_tracker.update(period_ms)
        if steady_ns > 0:
            self._last_imu_steady_for_period = steady_ns

    def get_imu_pipeline_status(self) -> ImuPipelineStatus:
        """Return current IMU pipeline status snapshot."""
        ring = self._imu_period_ring
        n = len(ring)
        if n < 2:
            return ImuPipelineStatus(
                ready=False, recent_count=n,
                latest_steady_ns=self._last_imu_steady_for_period)

        # Compute stats over the ring buffer
        mean_p = sum(ring) / n
        var_p = sum((x - mean_p) ** 2 for x in ring) / (n - 1)
        std_p = math.sqrt(var_p) if var_p > 0 else 0.0
        span = sum(ring)

        return ImuPipelineStatus(
            ready=self._check_imu_ready_local(n, mean_p, std_p, span),
            recent_count=n,
            mean_period_ms=mean_p,
            std_period_ms=std_p,
            span_ms=span,
            latest_steady_ns=self._last_imu_steady_for_period,
        )

    def _check_imu_ready_local(
        self, count: int, mean_ms: float, std_ms: float, span_ms: float,
    ) -> bool:
        """Check if local IMU stats satisfy readiness criteria."""
        cfg = self.cfg
        if count < cfg.sync_wait_imu_ready_min_samples:
            return False
        if span_ms < cfg.sync_wait_imu_ready_min_span_ms:
            return False
        if std_ms > cfg.sync_wait_imu_ready_max_std_ms:
            return False
        # mean period should be roughly 5 ms (±3 ms tolerance for 200 Hz)
        if not (2.0 <= mean_ms <= 8.0):
            return False
        return True

    def imu_pipeline_ready(self) -> bool:
        """Check if IMU pipeline is ready (external OR local)."""
        if self._external_imu_ready:
            return True
        status = self.get_imu_pipeline_status()
        return status.ready

    # ── camera startup drop check ────────────────────────────────────

    def _camera_startup_drop_done(self, now_mono: float) -> bool:
        """Return True when the camera startup drop period has elapsed."""
        elapsed = now_mono - self._startup_mono
        return elapsed >= self.cfg.camera_startup_drop_sec

    # ── 2a. Timestamp validation (§13.4) ─────────────────────────────

    def _check_imu_monotonic(self, t: float) -> bool:
        """Return *True* if *t* is acceptable.

        If *t* regresses beyond the tolerance threshold the pipeline is
        reset.  Exact duplicates are silently dropped.

        **Must be called while holding ``_imu_lock``.**  Resets the IMU
        state directly and defers the image-side reset to avoid
        deadlock.
        """
        if self._last_imu_t == 0.0:
            return True

        delta = t - self._last_imu_t
        if delta < 0:
            if abs(delta) > self.cfg.timestamp_regression_threshold_sec:
                self.stats.timestamp_anomaly_count += 1
                self._log('warn',
                          f'IMU timestamp regression {delta*1e3:.2f} ms '
                          f'→ pipeline reset')
                # Reset IMU state in-place (we already hold imu_lock)
                self._reset_imu_unlocked()
                # Defer image-side + shared state reset
                self._deferred_img_reset = True
                self._prev_aligned_steady_t = 0.0
                self.stats.reset_count += 1
                self._log('warn', 'Pipeline reset: imu_timestamp_regression')
                # Also rearm state machine
                self._force_rearm_from_reset()
                return False  # caller should discard this sample
            # small jitter → ignore
            return False
        if delta == 0.0:
            # exact duplicate
            self.stats.timestamp_anomaly_count += 1
            return False
        return True

    def _check_img_monotonic(self, t: float) -> bool:
        """Return *True* if *t* is acceptable (image stream).

        **Must be called while holding ``_img_lock``.**
        """
        if self._last_img_t == 0.0:
            return True

        delta = t - self._last_img_t
        if delta < 0:
            if abs(delta) > self.cfg.timestamp_regression_threshold_sec:
                self.stats.timestamp_anomaly_count += 1
                self._log('warn',
                          f'Image timestamp regression {delta*1e3:.2f} ms '
                          f'→ pipeline reset')
                # Reset image state in-place (we already hold img_lock)
                self._reset_img_unlocked()
                # Defer IMU-side + shared state reset
                self._deferred_imu_reset = True
                self._prev_aligned_steady_t = 0.0
                self.stats.reset_count += 1
                self._log('warn', 'Pipeline reset: img_timestamp_regression')
                self._force_rearm_from_reset()
                return False
            return False
        if delta == 0.0:
            self.stats.timestamp_anomaly_count += 1
            return False
        return True

    def _force_rearm_from_reset(self) -> None:
        """Rearm state machine on pipeline reset (safe from any context)."""
        self._state = SyncState.WAIT_IMU_READY
        self._first_sync_done = False
        self._consecutive_fail_count = 0
        self._first_sync_wait_start = 0.0
        self._first_sync_drop_count = 0
        self._imu_period_tracker.reset()
        self._imu_period_ring.clear()
        self._last_imu_steady_for_period = 0
        self._external_imu_ready = False

    # ── 2b. IMU input (§5 imu-recv thread) ───────────────────────────

    def on_imu(self, t: float, msg, now_mono: Optional[float] = None,
               *, steady_ns: int = 0) -> int:
        """Enqueue an incoming IMU sample.

        Parameters
        ----------
        t : float
            Header timestamp in seconds (observation only).
        msg : Imu
            The raw IMU message.
        now_mono : float, optional
            ``time.monotonic()`` at call time (injected for testing).
        steady_ns : int
            ``time.monotonic_ns()`` — nanosecond-precision monotonic
            clock.  **This is the primary time for sync decisions.**

        Returns
        -------
        int
            Assigned ``imu_id`` (>0) on success, 0 if rejected.
        """
        if now_mono is None:
            now_mono = self._clock()

        with self._imu_lock:
            # Apply any deferred reset from image-side
            if self._deferred_imu_reset:
                self._reset_imu_unlocked()
                self._deferred_imu_reset = False

            if not self._check_imu_monotonic(t):
                return 0

            imu_id = self._next_imu_id
            self._next_imu_id += 1

            self._last_imu_t = t
            self._last_imu_mono = now_mono
            self._imu_buf.append((t, msg, imu_id, steady_ns))

            # Update latest steady time
            if steady_ns > 0:
                steady_sec = steady_ns / 1e9
                if steady_sec > self._latest_imu_steady_sec:
                    self._latest_imu_steady_sec = steady_sec

            # trim stale data (by header time for buffer management)
            cutoff = t - self.cfg.imu_buffer_sec
            while self._imu_buf and self._imu_buf[0][0] < cutoff:
                self._imu_buf.popleft()

        # Update period tracker (outside imu_lock — ok, tracker is
        # only read from try_sync which runs in drain thread)
        self._update_imu_period_tracker(steady_ns)

        return imu_id

    # ── 2c. Image input (§5 img-recv thread) ─────────────────────────

    def on_image(self, t_cam: float, msg, now_mono: Optional[float] = None,
                 *, steady_ns: int = 0, cam_header_ns: int = 0) -> int:
        """Enqueue an incoming camera frame.

        Parameters
        ----------
        t_cam : float
            Header timestamp of the camera frame in seconds.
        msg : Image
            The raw Image message.
        now_mono : float, optional
            ``time.monotonic()`` at call time (injected for testing).
        steady_ns : int
            ``time.monotonic_ns()`` for sync decisions.
        cam_header_ns : int
            Original camera header timestamp in nanoseconds.

        Returns
        -------
        int
            Assigned ``cam_frame_id`` (>0) on success, 0 if rejected.
        """
        if now_mono is None:
            now_mono = self._clock()

        # §5.8 – camera startup drop
        if not self._camera_startup_drop_done(now_mono):
            self.stats.camera_startup_drops += 1
            return 0

        with self._img_lock:
            # Apply any deferred reset from IMU-side
            if self._deferred_img_reset:
                self._reset_img_unlocked()
                self._deferred_img_reset = False

            if not self._check_img_monotonic(t_cam):
                return 0

            cam_frame_id = self._next_cam_frame_id
            self._next_cam_frame_id += 1

            self._last_img_t = t_cam

            # Header-domain alignment (legacy, for ROS output only)
            t_align = t_cam + self.cfg.cam_imu_time_offset

            # STEADY-domain alignment (PRIMARY sync target)
            cam_steady_sec = steady_ns / 1e9 if steady_ns > 0 else now_mono
            t_align_steady = cam_steady_sec + self.cfg.steady_cam_to_imu_offset_sec

            # §13.5 – queue overflow protection
            if len(self._img_queue) >= self.cfg.max_image_queue_size:
                dropped = self._img_queue.popleft()
                self.stats.queue_overflow_count += 1
                self.stats.dropped_frames += 1
                self._log('warn',
                          f'Image queue overflow – dropped oldest frame '
                          f't_cam={dropped.t_cam:.3f}')

            # §13.5 – backlog warning
            if (self.cfg.warn_on_queue_backlog
                    and len(self._img_queue)
                    >= int(self.cfg.max_image_queue_size * 0.7)):
                self._log('warn',
                          f'Image queue backlog: '
                          f'{len(self._img_queue)}/'
                          f'{self.cfg.max_image_queue_size}')

            self._img_queue.append(
                FrameSample(t_cam=t_cam, t_align=t_align,
                            t_align_steady=t_align_steady,
                            enqueued_mono=now_mono, msg=msg,
                            cam_frame_id=cam_frame_id,
                            steady_ns=steady_ns,
                            cam_header_ns=cam_header_ns))

        # Phase 1A: track camera inter-arrival stability
        self._update_cam_period_tracker(steady_ns)

        return cam_frame_id

    # ── 2d. Synchronisation attempt — state machine dispatch ─────────

    def try_sync(self, now_mono: Optional[float] = None
                 ) -> Optional[SyncBatch]:
        """Attempt to produce a synchronised batch.

        Returns *None* when not enough data is available yet (or after
        a timeout / drop / state-machine wait).  The caller should call
        this in a loop until it returns *None*.

        Parameters
        ----------
        now_mono : float, optional
            ``time.monotonic()`` at call time.

        Returns
        -------
        SyncBatch or None
        """
        if now_mono is None:
            now_mono = self._clock()

        # Apply any deferred cross-lock resets before proceeding
        self._apply_deferred_resets()

        if self._state == SyncState.INIT:
            # Phase 1A: INIT → WAIT_IMU_READY on first call
            self._transition_to(SyncState.WAIT_IMU_READY)
            return None
        if self._state == SyncState.WAIT_IMU_READY:
            return self._try_wait_imu_ready(now_mono)
        elif self._state == SyncState.WAIT_CAM_STABLE:
            return self._try_wait_cam_stable(now_mono)
        elif self._state == SyncState.WAIT_FIRST_SYNC:
            return self._try_wait_first_sync(now_mono)
        elif self._state == SyncState.DEGRADED:
            # DEGRADED: attempt re-arm after a while
            return self._try_wait_imu_ready(now_mono)
        else:  # READY
            return self._try_ready_sync(now_mono)

    # ── Phase 1: WAIT_IMU_READY ──────────────────────────────────────

    def _try_wait_imu_ready(self, now_mono: float) -> None:
        """Wait for IMU pipeline to stabilise before attempting sync."""
        if not self.imu_pipeline_ready():
            # Drain and discard any queued images to prevent buildup
            with self._img_lock:
                n_discarded = len(self._img_queue)
                if n_discarded > 0:
                    self._img_queue.clear()
                    self.stats.dropped_frames += n_discarded
            return None

        if not self._camera_startup_drop_done(now_mono):
            return None

        # Reset first-sync tracking
        self._first_sync_wait_start = now_mono
        self._first_sync_drop_count = 0

        # Phase 1A: go through WAIT_CAM_STABLE before WAIT_FIRST_SYNC
        if self.cfg.deterministic_sync:
            self._transition_to(SyncState.WAIT_CAM_STABLE)
        else:
            self._transition_to(SyncState.WAIT_FIRST_SYNC)
        return None  # don't attempt sync in same tick

    # ── Phase 1A: WAIT_CAM_STABLE ────────────────────────────────────

    def _try_wait_cam_stable(self, now_mono: float) -> None:
        """Wait for camera inter-arrival to stabilise.

        Phase 1A addition: ensures the camera stream is stable before
        attempting first synchronisation.
        """
        if self._check_cam_stable():
            self._transition_to(SyncState.WAIT_FIRST_SYNC)
            self._first_sync_wait_start = now_mono
            self._first_sync_drop_count = 0
            return None

        # Drain queued images while waiting to prevent buildup
        with self._img_lock:
            n_discarded = len(self._img_queue)
            if n_discarded > 0:
                self._img_queue.clear()
                self.stats.dropped_frames += n_discarded

        return None

    # ── Phase 2: WAIT_FIRST_SYNC (STEADY domain) ─────────────────────

    def _try_wait_first_sync(self, now_mono: float) -> Optional[SyncBatch]:
        """Wait for first camera frame with sufficient IMU coverage.

        ALL decisions use steady-domain timestamps:
        - target = cam_steady + steady_cam_to_imu_offset
        - coverage check: latest_imu_steady >= target + margin
        - interval search: IMU steady_ns
        """
        # Peek at the image queue
        with self._img_lock:
            if not self._img_queue:
                return None
            frame = self._img_queue[0]

        # STEADY DOMAIN target
        target_steady = frame.t_align_steady
        margin = self.cfg.first_sync_safety_margin_sec

        # Check IMU coverage in steady domain
        with self._imu_lock:
            if len(self._imu_buf) == 0:
                return None
            latest_imu_steady = self._latest_imu_steady_sec

        if latest_imu_steady < target_steady + margin:
            # Not enough IMU coverage yet — check for timeout/re-arm
            waited = now_mono - self._first_sync_wait_start

            if waited >= self.cfg.first_sync_timeout_sec:
                self._log('warn',
                          f'WAIT_FIRST_SYNC timeout ({waited:.2f}s) → re-arm')
                self._rearm_from_first_sync('first_sync_timeout')
                return None

            # Per-frame timeout – drop oldest and try next
            frame_waited = now_mono - frame.enqueued_mono
            if frame_waited >= self.cfg.max_sync_wait_sec:
                with self._img_lock:
                    if self._img_queue and self._img_queue[0] is frame:
                        self._img_queue.popleft()
                self.stats.dropped_frames += 1
                self.stats.sync_wait_timeout_count += 1
                self._first_sync_drop_count += 1
                self._log('warn',
                          f'WAIT_FIRST_SYNC drop #{self._first_sync_drop_count}'
                          f' t_cam={frame.t_cam:.3f}'
                          f' target_steady={target_steady:.6f}'
                          f' latest_imu_steady={latest_imu_steady:.6f}')

                if self._first_sync_drop_count >= self.cfg.first_sync_drop_limit:
                    self._log('warn',
                              f'WAIT_FIRST_SYNC drop limit '
                              f'({self.cfg.first_sync_drop_limit}) → re-arm')
                    self._rearm_from_first_sync('first_sync_drop_limit')
            return None

        # ── IMU coverage is sufficient — attempt first sync ──────────
        # Find the last IMU sample at or before target_steady (by steady)
        with self._img_lock:
            if not self._img_queue or self._img_queue[0] is not frame:
                return None
            self._img_queue.popleft()

        with self._imu_lock:
            imu_batch: list = []
            imu_id_batch: list[int] = []
            imu_sns_batch: list[int] = []
            consume_up_to = 0

            for idx, (t_hdr, imu_msg, imu_id, imu_sns) in enumerate(
                    self._imu_buf):
                imu_steady_sec = imu_sns / 1e9 if imu_sns > 0 else 0.0
                if imu_steady_sec <= target_steady:
                    imu_batch.append(imu_msg)
                    imu_id_batch.append(imu_id)
                    imu_sns_batch.append(imu_sns)
                    consume_up_to = idx + 1
                else:
                    break

            # Consume used samples
            for _ in range(consume_up_to):
                self._imu_buf.popleft()

        if not imu_batch:
            self._log('warn',
                      'WAIT_FIRST_SYNC: no IMU at target_steady, retrying')
            return None

        # ── Success! Set prev_aligned_steady_t and enter READY ───────
        self._prev_aligned_steady_t = target_steady
        self._first_sync_done = True
        self._consecutive_fail_count = 0
        self._first_sync_wait_start = 0.0
        self._first_sync_drop_count = 0
        self._transition_to(SyncState.READY)

        self.stats.synced_frames += 1
        self.stats.total_imu_published += len(imu_batch)

        return SyncBatch(
            imu_msgs=imu_batch,
            image_msg=frame.msg,
            t_aligned=frame.t_align,
            t_aligned_steady=target_steady,
            cam_frame_id=frame.cam_frame_id,
            cam_header_ns=frame.cam_header_ns,
            cam_steady_ns=frame.steady_ns,
            imu_ids=tuple(imu_id_batch),
            imu_steady_ns_list=tuple(imu_sns_batch),
            interp_used=False,
        )

    def _rearm_from_first_sync(self, reason: str) -> None:
        """Re-arm from WAIT_FIRST_SYNC back to WAIT_IMU_READY."""
        self._first_sync_wait_start = 0.0
        self._first_sync_drop_count = 0
        self.rearm(reason)

    # ── Phase 3: READY (normal sync, STEADY domain) ──────────────────

    def _try_ready_sync(self, now_mono: float) -> Optional[SyncBatch]:
        """Normal synchronisation with health monitoring.

        All decisions use steady-domain timestamps.
        """
        # ── phase 1: peek & decide (both locks held briefly) ─────────
        with self._img_lock:
            if not self._img_queue:
                return None
            frame = self._img_queue[0]

        target_steady = frame.t_align_steady

        with self._imu_lock:
            imu_empty = len(self._imu_buf) == 0
            latest_imu_steady = self._latest_imu_steady_sec

        # ── §5.6 failure detection (steady domain) ───────────────────
        if imu_empty:
            return self._handle_ready_no_imu(frame, now_mono)

        if latest_imu_steady < target_steady:
            # Not enough IMU data yet — might be temporary
            waited = now_mono - frame.enqueued_mono
            if waited < self.cfg.max_sync_wait_sec:
                return None  # keep waiting

            # Timeout – register failure
            return self._handle_ready_timeout(
                frame, now_mono, latest_imu_steady, target_steady)

        # ── Health check: steady-domain lag ──────────────────────────
        cam_steady_sec = frame.steady_ns / 1e9 if frame.steady_ns > 0 else 0.0
        if latest_imu_steady > 0 and cam_steady_sec > 0:
            cam_minus_imu_last_ms = (cam_steady_sec - latest_imu_steady) * 1e3
            if cam_minus_imu_last_ms > self.cfg.sync_fail_lag_threshold_sec * 1e3:
                self._register_sync_fail(
                    f'steady lag={cam_minus_imu_last_ms:.1f}ms > threshold')
                # Don't drop frame yet — let normal fail handling do it
                if self._consecutive_fail_count >= self.cfg.sync_fail_consecutive_limit:
                    return None
                # Fall through to attempt sync anyway

        # ── phase 2: snapshot extraction (locks held) ────────────────
        with self._img_lock:
            if not self._img_queue or self._img_queue[0] is not frame:
                return None  # frame was consumed concurrently
            self._img_queue.popleft()

        with self._imu_lock:
            imu_batch: list = []
            imu_id_batch: list[int] = []
            imu_sns_batch: list[int] = []
            imu_before = None
            imu_before_steady = 0.0
            imu_after = None
            imu_after_steady = 0.0
            consume_up_to = 0

            for idx, (t_hdr, imu_msg, imu_id, imu_sns) in enumerate(
                    self._imu_buf):
                imu_steady_sec = imu_sns / 1e9 if imu_sns > 0 else 0.0

                if imu_steady_sec <= self._prev_aligned_steady_t:
                    consume_up_to = idx + 1
                    continue
                if imu_steady_sec <= target_steady:
                    imu_batch.append(imu_msg)
                    imu_id_batch.append(imu_id)
                    imu_sns_batch.append(imu_sns)
                    imu_before = imu_msg
                    imu_before_steady = imu_steady_sec
                    consume_up_to = idx + 1
                else:
                    imu_after = imu_msg
                    imu_after_steady = imu_steady_sec
                    break

            for _ in range(consume_up_to):
                self._imu_buf.popleft()

        # ── §5.6 check: empty batch ──────────────────────────────────
        if not imu_batch:
            self._register_sync_fail(
                'no IMU in (prev_aligned_steady, target_steady] interval')
            # Don't update prev_aligned_steady_t
            return None

        # ── phase 3: interpolation (steady domain, no locks) ─────────
        interp_applied = False
        if (imu_before is not None and imu_after is not None):
            gap_steady = abs(imu_before_steady - target_steady)

            if gap_steady <= self.cfg.boundary_tolerance_sec:
                # already on the boundary – skip interpolation
                pass
            elif not self.cfg.enable_interpolation:
                # interpolation disabled → drop frame
                self.stats.dropped_frames += 1
                self._log('info',
                          'Interpolation disabled – frame dropped')
                return None
            else:
                # Check interpolation gap in steady domain
                interp_gap = imu_after_steady - imu_before_steady
                if interp_gap > self.cfg.max_interp_gap_sec:
                    self.stats.dropped_frames += 1
                    self._log('warn',
                              f'Interpolation gap too large '
                              f'({interp_gap*1e3:.1f} ms '
                              f'> {self.cfg.max_interp_gap_sec*1e3:.0f} ms)'
                              f' – frame dropped')
                    # still update prev to avoid re-processing
                    self._prev_aligned_steady_t = target_steady
                    return None

                interp_msg = lerp_imu_steady(
                    imu_before, imu_after,
                    imu_before_steady, imu_after_steady,
                    target_steady,
                    make_imu=self._make_imu)
                imu_batch.append(interp_msg)
                # Keep id/sns lists aligned with imu_batch
                imu_id_batch.append(-1)  # synthetic id for interpolated point
                imu_sns_batch.append(int(target_steady * 1e9))
                self.stats.interp_count += 1
                interp_applied = True

        self._prev_aligned_steady_t = target_steady
        self._consecutive_fail_count = 0  # success resets fail counter

        # ── phase 4: build result ────────────────────────────────────
        self.stats.synced_frames += 1
        self.stats.total_imu_published += len(imu_batch)

        return SyncBatch(
            imu_msgs=imu_batch,
            image_msg=frame.msg,
            t_aligned=frame.t_align,
            t_aligned_steady=target_steady,
            cam_frame_id=frame.cam_frame_id,
            cam_header_ns=frame.cam_header_ns,
            cam_steady_ns=frame.steady_ns,
            imu_ids=tuple(imu_id_batch),
            imu_steady_ns_list=tuple(imu_sns_batch),
            interp_used=interp_applied,
        )

    # ── failure handling helpers ──────────────────────────────────────

    def _handle_ready_no_imu(
        self, frame: FrameSample, now_mono: float,
    ) -> None:
        """Handle READY state with no IMU data at all."""
        waited = now_mono - frame.enqueued_mono
        if waited < self.cfg.max_sync_wait_sec:
            return None  # keep waiting

        # Timeout with no IMU → definite failure
        self._register_sync_fail('imu_empty_timeout')

        if self.cfg.drop_frame_on_missing_imu:
            with self._img_lock:
                if self._img_queue and self._img_queue[0] is frame:
                    self._img_queue.popleft()
            self.stats.dropped_frames += 1
            self.stats.sync_wait_timeout_count += 1

        # §13.2 IMU stream interruption check
        with self._imu_lock:
            imu_silence = now_mono - self._last_imu_mono \
                if self._last_imu_mono > 0 else 0.0
        if imu_silence > self.cfg.imu_stream_timeout_sec:
            self._log('warn',
                      f'IMU stream dead ({imu_silence:.1f} s) → rearm')
            self.rearm('imu_stream_dead')
        return None

    def _handle_ready_timeout(
        self, frame: FrameSample, now_mono: float,
        latest_imu_steady: float, target_steady: float,
    ) -> None:
        """Handle READY state sync-wait timeout (steady domain)."""
        lag = target_steady - latest_imu_steady

        self.stats.sync_wait_timeout_count += 1

        if lag > self.cfg.sync_fail_lag_threshold_sec:
            self._register_sync_fail(
                f'steady_lag={lag*1e3:.1f}ms > threshold')

        if self.cfg.drop_frame_on_missing_imu:
            with self._img_lock:
                if self._img_queue and self._img_queue[0] is frame:
                    self._img_queue.popleft()
            self.stats.dropped_frames += 1
            self._log('warn',
                      f'Sync timeout – dropped frame t={frame.t_cam:.3f} '
                      f'steady_lag={lag*1e3:.1f}ms')

        # §13.2 IMU stream interruption check
        with self._imu_lock:
            imu_silence = now_mono - self._last_imu_mono \
                if self._last_imu_mono > 0 else 0.0
        if imu_silence > self.cfg.imu_stream_timeout_sec:
            self._log('warn',
                      f'IMU stream dead ({imu_silence:.1f} s) → rearm')
            self.rearm('imu_stream_dead')
        return None

    def _register_sync_fail(self, reason: str) -> None:
        """Register a sync failure and rearm if threshold exceeded."""
        self.stats.sync_fail_count += 1
        self._consecutive_fail_count += 1
        self._log('warn',
                  f'Sync fail #{self._consecutive_fail_count}: {reason}')

        if self._consecutive_fail_count >= self.cfg.sync_fail_consecutive_limit:
            self.rearm(f'consecutive_fail({reason})')

    # ── rearm: return to WAIT_IMU_READY ──────────────────────────────

    def rearm(self, reason: str = 'unknown') -> None:
        """Re-arm: transition back to WAIT_IMU_READY.

        Clears image queue and sync state, but preserves IMU buffer
        (it may still contain valid data that's being accumulated).
        Resets the period tracker to force re-evaluation of readiness.
        """
        self._state = SyncState.WAIT_IMU_READY
        self._first_sync_done = False
        self._consecutive_fail_count = 0
        self._prev_aligned_steady_t = 0.0
        self._first_sync_wait_start = 0.0
        self._first_sync_drop_count = 0

        # Clear image queue
        with self._img_lock:
            self._reset_img_unlocked()

        # Reset period tracker (force re-evaluation)
        self._imu_period_tracker.reset()
        self._imu_period_ring.clear()
        self._last_imu_steady_for_period = 0

        # Clear external ready flag (force driver to re-signal)
        self._external_imu_ready = False

        self.stats.rearm_count += 1
        self._log('warn', f'Re-arm: {reason} → WAIT_IMU_READY')

    # ── 2e. Reset (§13.4) ───────────────────────────────────────────

    def reset(self, reason: str = 'unknown') -> None:
        """Clear all synchronisation state.

        Called on prolonged IMU silence or manual request.
        Both locks are acquired sequentially (never nested).
        """
        with self._imu_lock:
            self._reset_imu_unlocked()

        with self._img_lock:
            self._reset_img_unlocked()

        self._deferred_imu_reset = False
        self._deferred_img_reset = False
        self._prev_aligned_steady_t = 0.0

        # State machine reset
        self._state = SyncState.WAIT_IMU_READY
        self._first_sync_done = False
        self._consecutive_fail_count = 0
        self._first_sync_wait_start = 0.0
        self._first_sync_drop_count = 0
        self._imu_period_tracker.reset()
        self._imu_period_ring.clear()
        self._last_imu_steady_for_period = 0
        self._external_imu_ready = False

        self.stats.reset_count += 1
        self._log('warn', f'Pipeline reset: {reason}')
