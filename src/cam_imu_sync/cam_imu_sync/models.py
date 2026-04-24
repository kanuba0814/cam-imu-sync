#!/usr/bin/env python3
# Copyright 2026 gxxl. MIT License.
"""Data models for cam_imu_sync synchronisation pipeline.

Provides pure-Python dataclasses shared by :mod:`sync_manager` and
:mod:`sync_node`.  No ROS dependency – keeps the domain layer portable
and testable.
"""

from __future__ import annotations

import dataclasses
import enum
from typing import Any


# ── Sync state machine enum ─────────────────────────────────────────

class SyncState(enum.Enum):
    """Synchronisation state machine phases.

    Phase 1A extends the original three-phase model with INIT,
    WAIT_CAM_STABLE, and DEGRADED states.
    """
    INIT = "INIT"
    WAIT_IMU_READY = "WAIT_IMU_READY"
    WAIT_CAM_STABLE = "WAIT_CAM_STABLE"
    WAIT_FIRST_SYNC = "WAIT_FIRST_SYNC"
    READY = "READY"
    DEGRADED = "DEGRADED"


# ── IMU pipeline status ─────────────────────────────────────────────

@dataclasses.dataclass
class ImuPipelineStatus:
    """Snapshot of IMU pipeline health (§4.4).

    Published by the Driver via ``/imu/pipeline_ready`` topic
    (方案 B) and also tracked locally by the sync manager for
    fallback / additional monitoring.
    """
    ready: bool = False
    recent_count: int = 0
    mean_period_ms: float = 0.0
    std_period_ms: float = 0.0
    span_ms: float = 0.0
    latest_steady_ns: int = 0


# ── Sync configuration ──────────────────────────────────────────────

@dataclasses.dataclass
class SyncConfig:
    """Immutable bag of parameters driving the sync pipeline.

    All time values are in **seconds** internally; the launch layer
    converts millisecond arguments to seconds before constructing this
    object.
    """

    # ── existing parameters ──────────────────────────────────────────
    cam_imu_time_offset: float = 0.2745
    """Kalibr-calibrated timeshift (header domain, legacy/observation
    only).  **NOT** used for sync decisions – kept for ROS header
    stamping and backward-compatible diagnostics."""

    # ── NEW: steady-domain offset (drives ALL sync decisions) ────────
    steady_cam_to_imu_offset_sec: float = 0.05
    """Steady-domain offset: ``target_steady = cam_steady + offset``.
    This is the ONLY offset used in sync logic.  Estimated from
    steady-clock experiments (typically 30–80 ms)."""

    imu_buffer_sec: float = 3.0
    """Maximum age of retained IMU samples in the buffer."""

    enable_interpolation: bool = True
    """Whether to linearly interpolate a boundary IMU at t_aligned."""

    # ── existing parameters (§12 / §13) ──────────────────────────────
    max_sync_wait_sec: float = 0.100
    """§13.1 – maximum time (seconds) to wait for IMU before dropping
    a queued image frame.  Default 100 ms."""

    max_interp_gap_sec: float = 0.010
    """§13.3 – refuse interpolation when the gap between the two
    bracketing IMU samples exceeds this value.  Default 10 ms."""

    drop_frame_on_missing_imu: bool = True
    """§13.1 – if *True*, silently drop the image when the wait times
    out.  If *False*, the frame is re-queued (legacy behaviour)."""

    warn_on_queue_backlog: bool = True
    """§13.5 – emit a ``WARN`` log when image-queue occupancy exceeds
    70 % of *max_image_queue_size*."""

    max_image_queue_size: int = 20
    """§8.2 – upper bound on queued camera frames.  When exceeded the
    oldest frame is discarded."""

    # ── derived thresholds ───────────────────────────────────────────
    imu_stream_timeout_sec: float = 2.0
    """§13.2 – consider the IMU stream dead after this silence period."""

    timestamp_regression_threshold_sec: float = 0.001
    """§13.4 – timestamp regressions smaller than this are treated as
    jitter and silently ignored (not triggering a reset)."""

    boundary_tolerance_sec: float = 1e-4
    """0.1 ms tolerance for considering an IMU sample exactly on the
    boundary (skip interpolation)."""

    # ── NEW: startup & state-machine parameters ──────────────────────

    camera_startup_drop_sec: float = 1.0
    """§5.8 – discard camera frames for this duration after startup
    to avoid unstable USB/exposure initialisation data."""

    sync_wait_imu_ready_min_samples: int = 40
    """§5.2 – minimum IMU samples before declaring pipeline ready."""

    sync_wait_imu_ready_min_span_ms: float = 150.0
    """§5.2 – minimum time span (ms) of recent IMU data for ready."""

    sync_wait_imu_ready_max_std_ms: float = 1.0
    """§5.2 – maximum acceptable period std-dev (ms) for ready."""

    first_sync_safety_margin_sec: float = 0.005
    """§5.3 – extra margin (sec) beyond target_steady for first sync.
    ``latest_imu_steady >= target_steady + margin`` before allowed."""

    first_sync_timeout_sec: float = 2.0
    """Maximum seconds to wait in WAIT_FIRST_SYNC before re-arming."""

    first_sync_drop_limit: int = 60
    """Maximum camera frames dropped in WAIT_FIRST_SYNC before re-arm."""

    sync_fail_lag_threshold_sec: float = 0.100
    """§5.6 – steady-domain lag exceeding this → sync failure."""

    sync_fail_consecutive_limit: int = 5
    """§5.6 – consecutive sync failures before triggering re-arm."""

    # ── Phase 1A: deterministic sync parameters ──────────────────────

    deterministic_sync: bool = True
    """R7 – when True, use the Phase 1A unified time domain pipeline.
    When False, fall back to the legacy header-domain-only behaviour."""

    enable_header_rewrite: bool = True
    """R3 – when True (and deterministic_sync is True), the sync node
    rewrites ALL output header.stamp from the unified steady-to-ROS
    mapping.  When False, output headers pass through unchanged."""

    min_stable_cam_frames: int = 10
    """R4 – number of consecutive camera frames with stable inter-
    arrival period required before transitioning from WAIT_CAM_STABLE
    to WAIT_FIRST_SYNC."""

    cam_stable_max_std_ms: float = 10.0
    """Maximum acceptable camera inter-arrival period std-dev (ms)
    for the WAIT_CAM_STABLE → WAIT_FIRST_SYNC transition."""

    imu_raw_hw_topic: str = '/imu/raw_hw'
    """Topic name for the ImuRawHw messages (Phase 1A)."""


@dataclasses.dataclass
class FrameSample:
    """A camera frame queued for synchronisation."""

    t_cam: float
    """Original camera header timestamp in seconds (observation only)."""

    t_align: float
    """Header-domain aligned timestamp: ``t_cam + cam_imu_time_offset``.
    Legacy – used only for ROS output header stamping."""

    t_align_steady: float
    """Steady-domain aligned timestamp (seconds):
    ``cam_steady_sec + steady_cam_to_imu_offset_sec``.
    This is the PRIMARY sync target."""

    enqueued_mono: float
    """``time.monotonic()`` at enqueue time – used for timeout logic."""

    msg: Any
    """The underlying ``sensor_msgs/Image`` message (opaque here)."""

    cam_frame_id: int = 0
    """Sequential camera frame ID assigned by the manager."""

    steady_ns: int = 0
    """``time.monotonic_ns()`` when this frame was enqueued."""

    cam_header_ns: int = 0
    """Original camera header timestamp in nanoseconds."""


@dataclasses.dataclass
class SyncStats:
    """Cumulative synchronisation statistics (§14)."""

    synced_frames: int = 0
    """Number of successfully synced image frames."""

    dropped_frames: int = 0
    """Frames discarded (timeout, queue overflow, interp-gap …)."""

    interp_count: int = 0
    """Number of frames where boundary interpolation was applied."""

    total_imu_published: int = 0
    """Cumulative IMU messages forwarded downstream."""

    sync_wait_timeout_count: int = 0
    """§13.1 – count of sync-wait timeouts."""

    timestamp_anomaly_count: int = 0
    """§13.4 – count of timestamp regressions / duplicates."""

    queue_overflow_count: int = 0
    """§13.5 – count of image-queue overflow drops."""

    reset_count: int = 0
    """Number of full pipeline resets triggered."""

    # ── NEW: state-machine statistics ────────────────────────────────

    state_transitions: int = 0
    """Number of state machine transitions."""

    camera_startup_drops: int = 0
    """Camera frames discarded during startup drop window."""

    sync_fail_count: int = 0
    """Total sync failure events (imu_last==0, lag too large, etc.)."""

    rearm_count: int = 0
    """Number of re-arm transitions back to WAIT_IMU_READY."""


# ── Phase 1A: raw IMU sample from ImuRawHw message ─────────────────

@dataclasses.dataclass
class ImuRawSample:
    """Data extracted from a ``yesense_interface/ImuRawHw`` message.

    Phase 1A: only ``tid``, ``rx_steady_ns``, ``rx_ros_ns``, and
    inertial data are meaningful.  Hardware timestamp fields are
    reserved (always zero).
    """

    tid: int
    rx_steady_ns: int
    rx_ros_ns: int
    lin_acc: tuple  # (x, y, z) in m/s²
    ang_vel: tuple  # (x, y, z) in rad/s
    orientation: tuple  # (x, y, z, w) quaternion
    frame_id: str

    # Reserved (Phase 1A: all zero)
    sample_timestamp: int = 0
    data_ready_timestamp: int = 0
    hw_ts_unit_sec: float = 0.0

    # Assigned by sync manager
    imu_id: int = 0
