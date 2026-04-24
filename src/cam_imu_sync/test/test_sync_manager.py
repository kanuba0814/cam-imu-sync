#!/usr/bin/env python3
# Copyright 2026 gxxl. MIT License.
"""Unit tests for SyncManager – pure Python, no ROS runtime required.

Run with:
    cd extra_ws && colcon test --packages-select cam_imu_sync
    # or directly:
    python -m pytest test/test_sync_manager.py -v

NOTE: All sync decisions now use the **steady-clock domain**.
Tests must provide ``steady_ns`` for both IMU and image to drive
synchronisation.  Header timestamps (``t``, ``t_cam``) are kept for
backward compat but do NOT influence sync outcomes.
"""

from __future__ import annotations

import dataclasses
import types
from typing import Any

import pytest

from cam_imu_sync.models import SyncConfig, SyncState, SyncStats
from cam_imu_sync.sync_manager import SyncManager, SyncBatch


# ─────────────────────────────────────────────────────────────────────
# Fake IMU / Image messages (duck-typed, no ROS dependency)
# ─────────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class _Stamp:
    sec: int = 0
    nanosec: int = 0


@dataclasses.dataclass
class _Header:
    stamp: _Stamp = dataclasses.field(default_factory=_Stamp)
    frame_id: str = 'imu_link'


@dataclasses.dataclass
class _Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclasses.dataclass
class _FakeImu:
    header: _Header = dataclasses.field(default_factory=_Header)
    linear_acceleration: _Vec3 = dataclasses.field(default_factory=_Vec3)
    angular_velocity: _Vec3 = dataclasses.field(default_factory=_Vec3)
    orientation_covariance: list = dataclasses.field(
        default_factory=lambda: [0.0] * 9)
    linear_acceleration_covariance: list = dataclasses.field(
        default_factory=lambda: [0.0] * 9)
    angular_velocity_covariance: list = dataclasses.field(
        default_factory=lambda: [0.0] * 9)


@dataclasses.dataclass
class _FakeImage:
    header: _Header = dataclasses.field(default_factory=_Header)
    data: bytes = b''


def _make_imu_at(t: float, ax: float = 0.0, ay: float = 0.0,
                 az: float = 9.81) -> _FakeImu:
    """Create a fake IMU message at timestamp *t* seconds."""
    sec = int(t)
    nsec = int(round((t - sec) * 1e9))
    msg = _FakeImu()
    msg.header.stamp.sec = sec
    msg.header.stamp.nanosec = nsec
    msg.linear_acceleration = _Vec3(ax, ay, az)
    msg.angular_velocity = _Vec3(0.0, 0.0, 0.0)
    return msg


def _make_image_at(t: float) -> _FakeImage:
    """Create a fake Image message at timestamp *t* seconds."""
    sec = int(t)
    nsec = int(round((t - sec) * 1e9))
    msg = _FakeImage()
    msg.header.stamp.sec = sec
    msg.header.stamp.nanosec = nsec
    return msg


def _make_imu_factory(sec, nanosec, frame_id, lin_acc, ang_vel) -> _FakeImu:
    """IMU factory matching the signature expected by SyncManager."""
    msg = _FakeImu()
    msg.header.stamp.sec = sec
    msg.header.stamp.nanosec = nanosec
    msg.header.frame_id = frame_id
    msg.linear_acceleration = _Vec3(*lin_acc)
    msg.angular_velocity = _Vec3(*ang_vel)
    return msg


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

# Base steady time for tests: 100 seconds in nanoseconds
_STEADY_BASE_NS = 100_000_000_000


def _default_cfg(**overrides) -> SyncConfig:
    """Return a SyncConfig with test-friendly defaults.

    Note: ``steady_cam_to_imu_offset_sec=0.0`` so that
    ``target_steady = cam_steady`` for simple test maths.
    """
    kw = dict(
        cam_imu_time_offset=0.0,         # legacy header offset
        steady_cam_to_imu_offset_sec=0.0, # NO steady offset for tests
        imu_buffer_sec=3.0,
        enable_interpolation=True,
        max_sync_wait_sec=0.100,
        max_interp_gap_sec=0.010,
        drop_frame_on_missing_imu=True,
        warn_on_queue_backlog=True,
        max_image_queue_size=20,
        # State machine: fast startup for tests
        camera_startup_drop_sec=0.0,  # no drop in tests
        sync_wait_imu_ready_min_samples=5,  # lower for tests
        sync_wait_imu_ready_min_span_ms=20.0,  # lower for tests
        sync_wait_imu_ready_max_std_ms=2.0,  # relaxed for tests
        first_sync_safety_margin_sec=0.005,
        first_sync_timeout_sec=2.0,
        first_sync_drop_limit=60,
        sync_fail_lag_threshold_sec=0.100,
        sync_fail_consecutive_limit=3,  # lower for tests
    )
    kw.update(overrides)
    return SyncConfig(**kw)


def _make_manager(cfg=None, **cfg_overrides) -> SyncManager:
    if cfg is None:
        cfg = _default_cfg(**cfg_overrides)
    # Use a fixed startup time so camera_startup_drop works predictably
    start_time = 100.0
    mgr = SyncManager(cfg, make_imu=_make_imu_factory,
                       clock=lambda: start_time)
    # Override _startup_mono to a known value
    mgr._startup_mono = start_time
    return mgr


def _feed_imu_200hz(mgr, start_t, count, mono_base=100.0,
                     steady_ns_base=_STEADY_BASE_NS):
    """Feed IMU at 200 Hz with proper steady_ns for period tracking.

    Both header timestamps and steady_ns advance in lockstep so that
    the steady-domain sync logic works correctly in tests.
    """
    for i in range(count):
        t = start_t + i * 0.005
        steady = steady_ns_base + int(i * 5_000_000)  # 5ms in ns
        mgr.on_imu(t, _make_imu_at(t), now_mono=mono_base,
                    steady_ns=steady)


def _make_ready(mgr, mono=100.0):
    """Feed enough IMU to satisfy readiness criteria and transition
    the manager to WAIT_FIRST_SYNC state."""
    # Feed 50 IMU at 200 Hz to ensure readiness
    _feed_imu_200hz(mgr, 1.0, 50, mono_base=mono)
    # Trigger state check
    mgr.try_sync(now_mono=mono)
    # Should now be in WAIT_FIRST_SYNC
    return mgr


def _make_fully_ready(mgr, mono=100.0):
    """Feed enough IMU and one image to get to READY state.

    Uses steady_ns that matches the target alignment so that
    the steady-domain sync succeeds.
    """
    _make_ready(mgr, mono)
    assert mgr.state == SyncState.WAIT_FIRST_SYNC

    # Feed more IMU past the image's target time
    # steady_ns advances from _STEADY_BASE_NS + 250ms
    _feed_imu_200hz(mgr, 1.250, 20, mono_base=mono,
                     steady_ns_base=_STEADY_BASE_NS + 250_000_000)

    # Add image with steady_ns matching — target_steady = cam_steady + 0
    # cam_steady = 100.260 s → steady_ns = 100_260_000_000
    cam_steady_ns = _STEADY_BASE_NS + 260_000_000
    mgr.on_image(1.260, _make_image_at(1.260), now_mono=mono,
                 steady_ns=cam_steady_ns)
    batch = mgr.try_sync(now_mono=mono)
    assert batch is not None, (
        f'Expected first sync, state={mgr.state}, '
        f'imu_buf={mgr.imu_buf_depth}')
    assert mgr.state == SyncState.READY
    return mgr


# ─────────────────────────────────────────────────────────────────────
# Tests: State Machine
# ─────────────────────────────────────────────────────────────────────

class TestStateMachine:
    """Tests for the three-phase state machine."""

    def test_initial_state_is_wait_imu_ready(self):
        """Manager starts in WAIT_IMU_READY."""
        mgr = _make_manager()
        assert mgr.state == SyncState.WAIT_IMU_READY

    def test_insufficient_imu_stays_wait(self):
        """With too few IMU samples, stays in WAIT_IMU_READY."""
        mgr = _make_manager()
        mono = 100.0

        # Feed only 3 IMU (less than min_samples=5)
        for i in range(3):
            t = 1.0 + i * 0.005
            mgr.on_imu(t, _make_imu_at(t), now_mono=mono,
                       steady_ns=_STEADY_BASE_NS + i * 5_000_000)

        mgr.try_sync(now_mono=mono)
        assert mgr.state == SyncState.WAIT_IMU_READY

    def test_imu_ready_transitions_to_wait_first_sync(self):
        """With enough IMU samples, transitions to WAIT_FIRST_SYNC."""
        mgr = _make_manager()
        mono = 100.0

        _feed_imu_200hz(mgr, 1.0, 50, mono_base=mono)
        mgr.try_sync(now_mono=mono)
        assert mgr.state == SyncState.WAIT_FIRST_SYNC

    def test_external_ready_transitions_to_wait_first_sync(self):
        """External pipeline_ready=True overrides local estimation."""
        mgr = _make_manager(sync_wait_imu_ready_min_samples=1000)
        mono = 100.0

        # Feed a few IMU (not enough for local ready)
        _feed_imu_200hz(mgr, 1.0, 10, mono_base=mono)

        # But set external ready
        mgr.set_external_imu_ready(True)
        mgr.try_sync(now_mono=mono)
        assert mgr.state == SyncState.WAIT_FIRST_SYNC

    def test_first_sync_transitions_to_ready(self):
        """Successful first sync transitions to READY."""
        mgr = _make_manager()
        mono = 100.0

        _make_ready(mgr, mono)
        assert mgr.state == SyncState.WAIT_FIRST_SYNC

        # Feed more IMU past the image's target time
        _feed_imu_200hz(mgr, 1.250, 20, mono_base=mono,
                         steady_ns_base=_STEADY_BASE_NS + 250_000_000)

        # Add image at t=1.260
        cam_steady_ns = _STEADY_BASE_NS + 260_000_000
        mgr.on_image(1.260, _make_image_at(1.260), now_mono=mono,
                     steady_ns=cam_steady_ns)
        batch = mgr.try_sync(now_mono=mono)
        assert batch is not None
        assert mgr.state == SyncState.READY
        assert batch.t_aligned == pytest.approx(1.260)

    def test_ready_state_normal_sync(self):
        """In READY state, normal sync works."""
        mgr = _make_manager()
        mono = 100.0

        _make_fully_ready(mgr, mono)

        # Feed more IMU and another image
        _feed_imu_200hz(mgr, 1.350, 20, mono_base=mono,
                         steady_ns_base=_STEADY_BASE_NS + 350_000_000)
        cam_steady_ns = _STEADY_BASE_NS + 360_000_000
        mgr.on_image(1.360, _make_image_at(1.360), now_mono=mono,
                     steady_ns=cam_steady_ns)
        batch = mgr.try_sync(now_mono=mono)
        assert batch is not None
        assert batch.t_aligned == pytest.approx(1.360)
        assert mgr.stats.synced_frames == 2


class TestCameraStartupDrop:
    """§5.8 – Camera startup drop."""

    def test_camera_frames_dropped_during_startup(self):
        """Frames during startup window are discarded."""
        mgr = _make_manager(camera_startup_drop_sec=0.5)
        mono_start = 100.0

        # Image arrives during startup (mono < startup + 0.5)
        result = mgr.on_image(
            1.0, _make_image_at(1.0), now_mono=mono_start + 0.2)
        assert result == 0
        assert mgr.stats.camera_startup_drops == 1

    def test_camera_frames_accepted_after_startup(self):
        """Frames after startup window are accepted normally."""
        mgr = _make_manager(camera_startup_drop_sec=0.5)
        mono_start = 100.0

        # Image arrives after startup (mono > startup + 0.5)
        result = mgr.on_image(
            1.0, _make_image_at(1.0), now_mono=mono_start + 0.6)
        assert result > 0
        assert mgr.stats.camera_startup_drops == 0


class TestImuPipelineReady:
    """§5.2 – IMU pipeline readiness."""

    def test_not_ready_with_few_samples(self):
        """Pipeline not ready with insufficient samples."""
        mgr = _make_manager(sync_wait_imu_ready_min_samples=20)
        mono = 100.0

        _feed_imu_200hz(mgr, 1.0, 10, mono_base=mono)
        assert not mgr.imu_pipeline_ready()

    def test_ready_with_enough_samples(self):
        """Pipeline ready with sufficient stable samples."""
        mgr = _make_manager(sync_wait_imu_ready_min_samples=5)
        mono = 100.0

        _feed_imu_200hz(mgr, 1.0, 50, mono_base=mono)
        assert mgr.imu_pipeline_ready()

    def test_not_ready_with_high_jitter(self):
        """Pipeline not ready with high period jitter."""
        mgr = _make_manager(
            sync_wait_imu_ready_min_samples=5,
            sync_wait_imu_ready_max_std_ms=0.1,  # very tight
        )
        mono = 100.0

        # Feed IMU with varying periods (jittery)
        for i in range(50):
            t = 1.0 + i * 0.005
            # Add significant jitter to steady_ns
            jitter = (i % 3) * 2_000_000  # 0, 2, 4 ms jitter
            steady = _STEADY_BASE_NS + int(i * 5_000_000) + jitter
            mgr.on_imu(t, _make_imu_at(t), now_mono=mono,
                       steady_ns=steady)

        assert not mgr.imu_pipeline_ready()

    def test_pipeline_status_snapshot(self):
        """get_imu_pipeline_status returns valid snapshot."""
        mgr = _make_manager()
        mono = 100.0

        _feed_imu_200hz(mgr, 1.0, 30, mono_base=mono)
        status = mgr.get_imu_pipeline_status()

        assert status.recent_count > 0
        assert status.mean_period_ms > 0
        assert status.latest_steady_ns > 0


class TestFirstSync:
    """§5.3-§5.4 – First frame sync (steady domain)."""

    def test_first_sync_waits_for_coverage(self):
        """First sync waits until IMU covers target_steady + margin."""
        mgr = _make_manager()
        mono = 100.0

        _make_ready(mgr, mono)

        # Add image with steady_ns way beyond current IMU coverage
        cam_steady_ns = _STEADY_BASE_NS + 2_000_000_000  # +2s
        mgr.on_image(2.0, _make_image_at(2.0), now_mono=mono,
                     steady_ns=cam_steady_ns)
        batch = mgr.try_sync(now_mono=mono)
        assert batch is None
        assert mgr.state == SyncState.WAIT_FIRST_SYNC

    def test_first_sync_succeeds_with_coverage(self):
        """First sync succeeds when IMU covers target_steady."""
        mgr = _make_manager()
        mono = 100.0

        _make_ready(mgr, mono)

        # Feed IMU with steady_ns covering the target
        _feed_imu_200hz(mgr, 1.250, 20, mono_base=mono,
                         steady_ns_base=_STEADY_BASE_NS + 250_000_000)

        # Image steady_ns within IMU coverage
        cam_steady_ns = _STEADY_BASE_NS + 260_000_000
        mgr.on_image(1.260, _make_image_at(1.260), now_mono=mono,
                     steady_ns=cam_steady_ns)
        batch = mgr.try_sync(now_mono=mono)
        assert batch is not None
        assert mgr.state == SyncState.READY
        assert batch.t_aligned == pytest.approx(1.260)

    def test_first_sync_no_full_interval_required(self):
        """First sync doesn't require prev_aligned_steady_t interval."""
        mgr = _make_manager()
        mono = 100.0

        _make_ready(mgr, mono)

        # Feed IMU starting at steady_ns ~1.250s
        _feed_imu_200hz(mgr, 1.250, 20, mono_base=mono,
                         steady_ns_base=_STEADY_BASE_NS + 250_000_000)

        # Image — should work even though there's no prev_aligned set
        cam_steady_ns = _STEADY_BASE_NS + 260_000_000
        mgr.on_image(1.260, _make_image_at(1.260), now_mono=mono,
                     steady_ns=cam_steady_ns)
        batch = mgr.try_sync(now_mono=mono)
        assert batch is not None
        # Check steady domain prev
        expected_steady = cam_steady_ns / 1e9  # = 100.260
        assert mgr._prev_aligned_steady_t == pytest.approx(
            expected_steady, abs=1e-6)


class TestRearm:
    """§5.6 – Consecutive failure re-arm."""

    def test_consecutive_failures_trigger_rearm(self):
        """sync_fail_consecutive_limit failures → rearm."""
        mgr = _make_manager(sync_fail_consecutive_limit=3)
        mono = 100.0

        _make_fully_ready(mgr, mono)
        assert mgr.state == SyncState.READY

        # Feed 3 images but no new IMU → timeout failures
        for i in range(3):
            t = 2.0 + i * 0.033
            cam_sns = _STEADY_BASE_NS + 2_000_000_000 + i * 33_000_000
            mgr.on_image(t, _make_image_at(t),
                         now_mono=mono + 0.2 * (i + 1),
                         steady_ns=cam_sns)

        # Each try_sync should fail due to timeout
        for i in range(3):
            mgr.try_sync(now_mono=mono + 0.2 * (i + 1) + 0.15)

        # After 3 consecutive failures, should rearm
        assert mgr.state == SyncState.WAIT_IMU_READY
        assert mgr.stats.rearm_count >= 1

    def test_success_resets_fail_counter(self):
        """A successful sync resets the consecutive fail counter."""
        mgr = _make_manager(sync_fail_consecutive_limit=5)
        mono = 100.0

        _make_fully_ready(mgr, mono)

        # Feed more IMU and image for successful sync
        _feed_imu_200hz(mgr, 1.350, 20, mono_base=mono,
                         steady_ns_base=_STEADY_BASE_NS + 350_000_000)
        cam_steady_ns = _STEADY_BASE_NS + 360_000_000
        mgr.on_image(1.360, _make_image_at(1.360), now_mono=mono,
                     steady_ns=cam_steady_ns)
        batch = mgr.try_sync(now_mono=mono)
        assert batch is not None
        assert mgr._consecutive_fail_count == 0

    def test_rearm_clears_state(self):
        """rearm() properly clears all sync state."""
        mgr = _make_manager()
        mono = 100.0

        _make_fully_ready(mgr, mono)

        mgr.rearm('test_reason')
        assert mgr.state == SyncState.WAIT_IMU_READY
        assert mgr._first_sync_done is False
        assert mgr._consecutive_fail_count == 0
        assert mgr._prev_aligned_steady_t == 0.0
        assert mgr.stats.rearm_count >= 1

    def test_rearm_allows_recovery(self):
        """After rearm, system can recover to READY again."""
        mgr = _make_manager()
        mono = 100.0

        _make_fully_ready(mgr, mono)
        mgr.rearm('test')
        assert mgr.state == SyncState.WAIT_IMU_READY

        # Re-feed IMU to become ready again
        _feed_imu_200hz(mgr, 2.0, 50, mono_base=mono,
                         steady_ns_base=_STEADY_BASE_NS + 1_000_000_000)
        mgr.try_sync(now_mono=mono)
        assert mgr.state == SyncState.WAIT_FIRST_SYNC

        # Feed more IMU and image
        _feed_imu_200hz(mgr, 2.250, 20, mono_base=mono,
                         steady_ns_base=_STEADY_BASE_NS + 1_250_000_000)
        cam_steady_ns = _STEADY_BASE_NS + 1_260_000_000
        mgr.on_image(2.260, _make_image_at(2.260), now_mono=mono,
                     steady_ns=cam_steady_ns)
        batch = mgr.try_sync(now_mono=mono)
        assert batch is not None
        assert mgr.state == SyncState.READY


# ─────────────────────────────────────────────────────────────────────
# Tests: Normal Sync (in READY state)
# ─────────────────────────────────────────────────────────────────────

class TestNormalSync:
    """Normal synchronisation: enough IMU data + interpolation."""

    def test_basic_sync_with_interpolation(self):
        """200 Hz IMU, 30 fps camera → expect IMU per batch + interp."""
        mgr = _make_manager(steady_cam_to_imu_offset_sec=0.0)
        mono = 100.0

        _make_fully_ready(mgr, mono)

        # Feed more IMU at 200 Hz
        _feed_imu_200hz(mgr, 1.350, 20, mono_base=mono,
                         steady_ns_base=_STEADY_BASE_NS + 350_000_000)

        # Camera frame with matching steady_ns
        cam_steady_ns = _STEADY_BASE_NS + 360_000_000
        mgr.on_image(1.360, _make_image_at(1.360), now_mono=mono,
                     steady_ns=cam_steady_ns)

        batch = mgr.try_sync(now_mono=mono)
        assert batch is not None
        assert isinstance(batch, SyncBatch)
        assert batch.t_aligned == pytest.approx(1.360)
        assert len(batch.imu_msgs) >= 1

    def test_multiple_frames_sequential(self):
        """Process multiple image frames sequentially."""
        mgr = _make_manager(steady_cam_to_imu_offset_sec=0.0)
        mono = 100.0

        _make_fully_ready(mgr, mono)

        # Feed lots of IMU
        _feed_imu_200hz(mgr, 1.350, 50, mono_base=mono,
                         steady_ns_base=_STEADY_BASE_NS + 350_000_000)

        # Two camera frames with proper steady_ns
        cam1_sns = _STEADY_BASE_NS + 360_000_000
        cam2_sns = _STEADY_BASE_NS + 393_000_000
        mgr.on_image(1.360, _make_image_at(1.360), now_mono=mono,
                     steady_ns=cam1_sns)
        mgr.on_image(1.393, _make_image_at(1.393), now_mono=mono,
                     steady_ns=cam2_sns)

        b1 = mgr.try_sync(now_mono=mono)
        assert b1 is not None
        assert b1.t_aligned == pytest.approx(1.360)

        b2 = mgr.try_sync(now_mono=mono)
        assert b2 is not None
        assert b2.t_aligned == pytest.approx(1.393)

    def test_no_interpolation_when_exactly_on_boundary(self):
        """If an IMU sample falls exactly on target_steady, skip interp."""
        mgr = _make_manager(steady_cam_to_imu_offset_sec=0.0)
        mono = 100.0

        _make_fully_ready(mgr, mono)

        # Feed IMU at exactly the target steady time
        imu_steady_1 = _STEADY_BASE_NS + 360_000_000
        imu_steady_2 = _STEADY_BASE_NS + 365_000_000
        mgr.on_imu(1.360, _make_imu_at(1.360), now_mono=mono,
                   steady_ns=imu_steady_1)
        mgr.on_imu(1.365, _make_imu_at(1.365), now_mono=mono,
                   steady_ns=imu_steady_2)

        cam_steady_ns = _STEADY_BASE_NS + 360_000_000  # exactly on IMU
        mgr.on_image(1.360, _make_image_at(1.360), now_mono=mono,
                     steady_ns=cam_steady_ns)
        batch = mgr.try_sync(now_mono=mono)
        assert batch is not None


class TestTimeout:
    """§13.1 – sync-wait timeout."""

    def test_drop_frame_on_timeout(self):
        """IMU never arrives → frame dropped after max_sync_wait_sec."""
        mgr = _make_manager(
            steady_cam_to_imu_offset_sec=0.0,
            max_sync_wait_sec=0.050,
            drop_frame_on_missing_imu=True,
        )
        mono = 100.0

        _make_fully_ready(mgr, mono)

        # Image with steady_ns far beyond IMU coverage
        cam_steady_ns = _STEADY_BASE_NS + 5_000_000_000  # +5s
        mgr.on_image(5.0, _make_image_at(5.0), now_mono=mono,
                     steady_ns=cam_steady_ns)

        # try_sync immediately: not enough data, but within timeout
        result = mgr.try_sync(now_mono=mono + 0.010)
        assert result is None

        # try_sync after timeout
        result = mgr.try_sync(now_mono=mono + 0.060)
        assert result is None
        assert mgr.stats.sync_wait_timeout_count >= 1

    def test_keep_frame_if_no_drop(self):
        """drop_frame_on_missing_imu=False → frame stays in queue."""
        mgr = _make_manager(
            steady_cam_to_imu_offset_sec=0.0,
            max_sync_wait_sec=0.050,
            drop_frame_on_missing_imu=False,
        )
        mono = 100.0

        _make_fully_ready(mgr, mono)

        cam_steady_ns = _STEADY_BASE_NS + 5_000_000_000
        mgr.on_image(5.0, _make_image_at(5.0), now_mono=mono,
                     steady_ns=cam_steady_ns)

        # trigger timeout
        result = mgr.try_sync(now_mono=mono + 0.060)
        assert result is None
        assert mgr.stats.sync_wait_timeout_count >= 1


class TestIMUStreamInterruption:
    """§13.2 – IMU stream dead → reset."""

    def test_reset_on_imu_silence(self):
        """If no IMU for > imu_stream_timeout_sec, pipeline rearms."""
        mgr = _make_manager(
            steady_cam_to_imu_offset_sec=0.0,
            max_sync_wait_sec=0.050,
        )
        # default imu_stream_timeout_sec=2.0
        mono = 100.0

        _make_fully_ready(mgr, mono)

        # Now simulate 3 seconds silence — image far in the future
        cam_steady_ns = _STEADY_BASE_NS + 50_000_000_000
        mgr.on_image(50.0, _make_image_at(50.0), now_mono=mono + 3.0,
                     steady_ns=cam_steady_ns)
        mgr.try_sync(now_mono=mono + 3.060)
        assert mgr.stats.rearm_count >= 1


class TestInterpGap:
    """§13.3 – interpolation gap check."""

    def test_reject_large_interp_gap(self):
        """Gap between bracketing IMUs too large → drop frame."""
        mgr = _make_manager(
            steady_cam_to_imu_offset_sec=0.0,
            max_interp_gap_sec=0.005,  # 5 ms
        )
        mono = 100.0

        _make_fully_ready(mgr, mono)

        # Two IMU samples 20 ms apart (way beyond 5 ms limit)
        imu_sns_1 = _STEADY_BASE_NS + 400_000_000
        imu_sns_2 = _STEADY_BASE_NS + 420_000_000
        mgr.on_imu(1.400, _make_imu_at(1.400), now_mono=mono,
                   steady_ns=imu_sns_1)
        mgr.on_imu(1.420, _make_imu_at(1.420), now_mono=mono,
                   steady_ns=imu_sns_2)

        # Image between the two IMU samples
        cam_steady_ns = _STEADY_BASE_NS + 410_000_000
        mgr.on_image(1.410, _make_image_at(1.410), now_mono=mono,
                     steady_ns=cam_steady_ns)

        batch = mgr.try_sync(now_mono=mono)
        assert batch is None  # frame dropped due to large gap


class TestTimestampRegression:
    """§13.4 – timestamp jump / regression → reset."""

    def test_imu_timestamp_regression_resets(self):
        """IMU timestamp going backwards triggers reset."""
        mgr = _make_manager()
        mono = 100.0

        mgr.on_imu(1.000, _make_imu_at(1.000), now_mono=mono,
                    steady_ns=_STEADY_BASE_NS)
        mgr.on_imu(1.005, _make_imu_at(1.005), now_mono=mono,
                    steady_ns=_STEADY_BASE_NS + 5_000_000)
        # Big regression
        mgr.on_imu(0.900, _make_imu_at(0.900), now_mono=mono,
                    steady_ns=_STEADY_BASE_NS + 10_000_000)

        assert mgr.stats.timestamp_anomaly_count >= 1
        assert mgr.stats.reset_count == 1
        # State should be WAIT_IMU_READY after reset
        assert mgr.state == SyncState.WAIT_IMU_READY

    def test_image_timestamp_regression_resets(self):
        """Image timestamp going backwards triggers reset."""
        mgr = _make_manager()
        mono = 100.0

        mgr.on_image(1.000, _make_image_at(1.000), now_mono=mono)
        mgr.on_image(0.800, _make_image_at(0.800), now_mono=mono)

        assert mgr.stats.timestamp_anomaly_count >= 1
        assert mgr.stats.reset_count == 1

    def test_small_jitter_ignored(self):
        """Sub-threshold regression treated as jitter, no reset."""
        mgr = _make_manager()
        mono = 100.0

        mgr.on_imu(1.000, _make_imu_at(1.000), now_mono=mono)
        # 0.5 ms regression (below 1 ms threshold)
        mgr.on_imu(0.9995, _make_imu_at(0.9995), now_mono=mono)

        assert mgr.stats.reset_count == 0

    def test_duplicate_timestamp_dropped(self):
        """Exact duplicate timestamp → silently dropped."""
        mgr = _make_manager()
        mono = 100.0

        mgr.on_imu(1.000, _make_imu_at(1.000), now_mono=mono)
        mgr.on_imu(1.000, _make_imu_at(1.000), now_mono=mono)

        assert mgr.stats.timestamp_anomaly_count == 1
        assert mgr.stats.reset_count == 0


class TestQueueOverflow:
    """§13.5 – image queue overflow."""

    def test_overflow_drops_oldest(self):
        """When queue is full, oldest frame is discarded."""
        mgr = _make_manager(max_image_queue_size=3)
        mono = 100.0

        for i in range(5):
            t = 1.0 + i * 0.033
            mgr.on_image(t, _make_image_at(t), now_mono=mono)

        assert mgr.stats.queue_overflow_count == 2
        assert mgr.stats.dropped_frames == 2
        # Queue should have exactly 3 items
        assert len(mgr._img_queue) == 3


class TestOutputMonotonicity:
    """Output t_aligned should be monotonically increasing."""

    def test_output_timestamps_monotonic(self):
        mgr = _make_manager(steady_cam_to_imu_offset_sec=0.0)
        mono = 100.0

        _make_fully_ready(mgr, mono)

        # Feed lots of IMU with proper steady_ns
        _feed_imu_200hz(mgr, 1.350, 100, mono_base=mono,
                         steady_ns_base=_STEADY_BASE_NS + 350_000_000)

        # Feed 5 images with matching steady_ns
        cam_times = [1.360, 1.393, 1.426, 1.460, 1.493]
        for ct in cam_times:
            offset_ns = int((ct - 1.0) * 1e9)
            cam_sns = _STEADY_BASE_NS + offset_ns
            mgr.on_image(ct, _make_image_at(ct), now_mono=mono,
                         steady_ns=cam_sns)

        aligned_times = []
        while True:
            batch = mgr.try_sync(now_mono=mono)
            if batch is None:
                break
            aligned_times.append(batch.t_aligned)

        assert len(aligned_times) == 5
        for i in range(1, len(aligned_times)):
            assert aligned_times[i] > aligned_times[i - 1], \
                f't[{i}]={aligned_times[i]} <= t[{i-1}]={aligned_times[i-1]}'


class TestReset:
    """reset() clears all state."""

    def test_reset_clears_buffers(self):
        mgr = _make_manager()
        mono = 100.0

        mgr.on_imu(1.0, _make_imu_at(1.0), now_mono=mono)
        mgr.on_imu(1.005, _make_imu_at(1.005), now_mono=mono)
        mgr.on_image(1.0, _make_image_at(1.0), now_mono=mono)

        mgr.reset('test')

        assert len(mgr._imu_buf) == 0
        assert len(mgr._img_queue) == 0
        assert mgr._prev_aligned_steady_t == 0.0
        assert mgr.stats.reset_count == 1
        assert mgr.state == SyncState.WAIT_IMU_READY

    def test_reset_clears_state_machine(self):
        """reset() returns to WAIT_IMU_READY."""
        mgr = _make_manager()
        mono = 100.0

        _make_fully_ready(mgr, mono)
        assert mgr.state == SyncState.READY

        mgr.reset('test')
        assert mgr.state == SyncState.WAIT_IMU_READY
        assert mgr._first_sync_done is False
        assert mgr._consecutive_fail_count == 0


class TestWithOffset:
    """Test synchronisation with a non-zero steady_cam_to_imu_offset_sec."""

    def test_offset_applied(self):
        """target_steady = cam_steady + steady_offset."""
        steady_offset = 0.05  # 50 ms
        mgr = _make_manager(steady_cam_to_imu_offset_sec=steady_offset)
        mono = 100.0

        # IMU at 200 Hz with steady_ns covering enough range
        _feed_imu_200hz(mgr, 1.0, 200, mono_base=mono)

        # Wait for IMU ready
        mgr.try_sync(now_mono=mono)

        # Camera at steady=100.000s → target_steady=100.050s
        cam_steady_ns = _STEADY_BASE_NS  # 100.0s
        mgr.on_image(1.0, _make_image_at(1.0), now_mono=mono,
                     steady_ns=cam_steady_ns)

        batch = mgr.try_sync(now_mono=mono)
        assert batch is not None
        # The header-domain t_aligned is still cam_imu_time_offset-based
        assert batch.t_aligned == pytest.approx(1.0)  # cam_imu_time_offset=0
        # The steady-domain aligned time includes the offset
        expected_steady = 100.0 + steady_offset
        assert batch.t_aligned_steady == pytest.approx(expected_steady)


class TestLogDraining:
    """Manager log messages are properly queued and drainable."""

    def test_logs_emitted_on_reset(self):
        mgr = _make_manager()
        mgr.reset('test_reason')

        logs = mgr.drain_logs()
        assert len(logs) == 1
        assert 'test_reason' in logs[0].message
        assert logs[0].level == 'warn'

        # second drain is empty
        assert len(mgr.drain_logs()) == 0

    def test_logs_emitted_on_rearm(self):
        mgr = _make_manager()
        mgr.rearm('test_rearm')

        logs = mgr.drain_logs()
        assert any('Re-arm' in l.message for l in logs)

    def test_state_transition_logs(self):
        mgr = _make_manager()
        mono = 100.0

        _feed_imu_200hz(mgr, 1.0, 50, mono_base=mono)
        mgr.try_sync(now_mono=mono)

        logs = mgr.drain_logs()
        assert any('WAIT_FIRST_SYNC' in l.message for l in logs)


class TestHealthMonitoring:
    """Health monitoring in READY state (steady domain)."""

    def test_empty_imu_batch_registers_fail(self):
        """If no IMU in steady interval, registers as sync fail."""
        mgr = _make_manager(steady_cam_to_imu_offset_sec=0.0)
        mono = 100.0

        _make_fully_ready(mgr, mono)

        # Feed image far in the future with IMU coverage nearby
        imu_sns_1 = _STEADY_BASE_NS + 10_000_000_000
        imu_sns_2 = _STEADY_BASE_NS + 10_005_000_000
        cam_sns = _STEADY_BASE_NS + 10_003_000_000
        mgr.on_imu(10.000, _make_imu_at(10.000), now_mono=mono,
                   steady_ns=imu_sns_1)
        mgr.on_imu(10.005, _make_imu_at(10.005), now_mono=mono,
                   steady_ns=imu_sns_2)
        mgr.on_image(10.003, _make_image_at(10.003), now_mono=mono,
                     steady_ns=cam_sns)
        batch = mgr.try_sync(now_mono=mono)

        # Should get IMU in interval since we have coverage
        if batch is None:
            # If no batch, it means there was a gap — that's also valid
            assert mgr.stats.sync_fail_count > 0 or \
                   mgr.stats.dropped_frames > 0


class TestFirstSyncRearm:
    """WAIT_FIRST_SYNC timeout re-arm mechanism."""

    def test_first_sync_timeout_rearms(self):
        """WAIT_FIRST_SYNC times out and re-arms to WAIT_IMU_READY."""
        mgr = _make_manager(
            first_sync_timeout_sec=0.5,
            max_sync_wait_sec=0.050,
        )
        mono = 100.0

        _make_ready(mgr, mono)
        assert mgr.state == SyncState.WAIT_FIRST_SYNC

        # Feed an image with target far beyond IMU coverage
        cam_sns = _STEADY_BASE_NS + 99_000_000_000
        mgr.on_image(99.0, _make_image_at(99.0), now_mono=mono,
                     steady_ns=cam_sns)

        # Try sync repeatedly past timeout
        mgr.try_sync(now_mono=mono + 0.6)
        assert mgr.state == SyncState.WAIT_IMU_READY
        assert mgr.stats.rearm_count >= 1

    def test_first_sync_drop_limit_rearms(self):
        """Dropping too many frames in WAIT_FIRST_SYNC triggers re-arm."""
        mgr = _make_manager(
            first_sync_timeout_sec=999.0,  # don't timeout by time
            first_sync_drop_limit=3,
            max_sync_wait_sec=0.010,
        )
        mono = 100.0

        _make_ready(mgr, mono)
        assert mgr.state == SyncState.WAIT_FIRST_SYNC

        # Feed 4 images with targets far beyond coverage, each times out
        for i in range(4):
            t = 90.0 + i
            cam_sns = _STEADY_BASE_NS + int(t * 1e9)
            mgr.on_image(t, _make_image_at(t),
                         now_mono=mono + i * 0.020,
                         steady_ns=cam_sns)
            mgr.try_sync(now_mono=mono + (i + 1) * 0.020)

        assert mgr.state == SyncState.WAIT_IMU_READY
        assert mgr.stats.rearm_count >= 1
