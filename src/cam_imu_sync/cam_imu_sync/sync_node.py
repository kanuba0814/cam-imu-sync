#!/usr/bin/env python3
# Copyright 2026 gxxl. MIT License.
"""Camera-IMU time-offset synchronisation node (ROS 2 glue layer).

Subscribes to raw camera and IMU topics, compensates for the known
Kalibr-calibrated time offset  ``t_imu = t_cam + offset``,  and
republishes both streams on synchronised output topics.

This module is a thin **ROS adapter** around :class:`SyncManager`
(which contains all algorithm logic and is testable without ROS).

Strategy
--------
1. Buffer incoming IMU messages via ``SyncManager.on_imu()``.
2. Queue incoming camera frames via ``SyncManager.on_image()``.
3. A 200 Hz timer ("drain") calls ``SyncManager.try_sync()`` in a loop:
   - If a batch is returned → publish IMU batch then re-stamped image.
   - If *None* → nothing to do this tick.
4. A 1 Hz timer logs aggregated diagnostics (§14).

Steady-Domain Principle
-----------------------
All synchronisation decisions use ``time.monotonic_ns()`` (steady clock).
Header-domain timestamps (``header.stamp``) are preserved for ROS
output messages and diagnostic observation only.

State Machine
-------------
The sync manager uses a three-phase state machine:

* ``WAIT_IMU_READY``  – waits for IMU pipeline to stabilise
  (external ``/imu/pipeline_ready`` topic **or** local estimation).
* ``WAIT_FIRST_SYNC`` – waits for first camera frame with sufficient
  IMU coverage **in the steady-clock domain**.
* ``READY``           – normal synchronisation with health monitoring
  and automatic re-arm on consecutive failures.

Diagnostics
-----------
All debug records are printed through the ROS 2 logger via
:class:`DiagnosticsWriter`.  ``ros2 launch`` captures the terminal output in
the standard ROS 2 log directory.
"""

from __future__ import annotations

import time as _time

import rclpy
import rclpy.callback_groups
import rclpy.executors
from builtin_interfaces.msg import Time as TimeMsg
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image, Imu
from std_msgs.msg import Bool

from .diagnostics import (
    DiagnosticsWriter, NullDiagnosticsWriter, OnlineStats, build_run_meta)
from .fixed_rate_resampler import FixedRateImuResampler
from .models import ImuRawSample, SyncConfig
from .sync_manager import SyncManager, stamp2sec, sec2stamp


def _stamp_to_ns(stamp) -> int:
    """Convert a ROS ``builtin_interfaces/Time`` to nanoseconds."""
    return stamp.sec * 1_000_000_000 + stamp.nanosec


def _safe_rclpy_shutdown() -> None:
    """Shut rclpy down once, tolerating launch Ctrl-C ordering."""
    if rclpy.ok():
        rclpy.shutdown()


def _reliable_qos(depth: int) -> QoSProfile:
    """Build a RELIABLE, volatile QoS profile with a positive depth."""
    return QoSProfile(
        depth=max(1, int(depth)),
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE)


def _best_effort_qos(depth: int) -> QoSProfile:
    """Build a BEST_EFFORT, volatile QoS profile with a positive depth."""
    return QoSProfile(
        depth=max(1, int(depth)),
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE)


def _input_imu_rate_hz(
    window_rate_hz: float, mean_period_ms: float,
) -> float:
    """Return the best current estimate of received input IMU rate."""
    if window_rate_hz > 0.0:
        return window_rate_hz
    if mean_period_ms > 0.0:
        return 1000.0 / mean_period_ms
    return 0.0


class CamImuSyncNode(Node):
    """Delay-synchronise camera and IMU with linear interpolation."""

    def __init__(self) -> None:
        super().__init__('cam_imu_sync_node')

        # ── parameters ────────────────────────────────────────────────
        self.declare_parameter('cam_imu_time_offset', 0.2745)
        self.declare_parameter('image_topic_in', '/image_raw')
        self.declare_parameter('imu_topic_in', '/imu/data_raw')
        self.declare_parameter('image_topic_out', '/sync/image_raw')
        self.declare_parameter('imu_topic_out', '/sync/imu')
        self.declare_parameter('imu_buffer_sec', 3.0)
        self.declare_parameter('enable_interpolation', True)
        self.declare_parameter('enable_resampled_imu', True)
        self.declare_parameter('resampled_imu_topic', '')
        self.declare_parameter('resampled_imu_rate_hz', 100.0)
        self.declare_parameter('resampled_imu_latency_ms', 20.0)
        self.declare_parameter('resampled_imu_max_gap_ms', 15.0)
        self.declare_parameter('publish_batch_imu', False)
        self.declare_parameter('batch_imu_topic', '/sync/imu_batch')
        # §12 / §13 parameters
        self.declare_parameter('max_sync_wait_ms', 100.0)
        self.declare_parameter('max_interp_gap_ms', 10.0)
        self.declare_parameter('drop_frame_on_missing_imu', True)
        self.declare_parameter('warn_on_queue_backlog', True)
        self.declare_parameter('max_image_queue_size', 20)
        # diagnostics parameters
        self.declare_parameter('debug_enable', False)
        self.declare_parameter('debug_expected_imu_rate_hz', 0.0)

        # ── state-machine parameters ─────────────────────────────────
        self.declare_parameter('camera_startup_drop_sec', 1.0)
        self.declare_parameter('sync_wait_imu_ready_min_samples', 40)
        self.declare_parameter('sync_wait_imu_ready_min_span_ms', 150.0)
        self.declare_parameter('sync_wait_imu_ready_max_std_ms', 1.0)
        self.declare_parameter('first_sync_safety_margin_ms', 5.0)
        self.declare_parameter('sync_fail_lag_threshold_ms', 100.0)
        self.declare_parameter('sync_fail_consecutive_limit', 5)

        # ── NEW: steady-domain parameters ─────────────────────────────
        self.declare_parameter('steady_cam_to_imu_offset_sec', 0.05)
        self.declare_parameter('first_sync_timeout_sec', 2.0)
        self.declare_parameter('first_sync_drop_limit', 60)

        # ── Phase 1A: deterministic sync parameters ───────────────────
        self.declare_parameter('deterministic_sync', True)
        self.declare_parameter('enable_header_rewrite', True)
        self.declare_parameter('imu_raw_hw_topic', '/imu/raw_hw')
        self.declare_parameter('raw_hw_qos_depth', 1000)
        self.declare_parameter('legacy_imu_qos_depth', 50)
        self.declare_parameter('executor_threads', 8)
        self.declare_parameter('min_stable_cam_frames', 10)
        self.declare_parameter('cam_stable_max_std_ms', 10.0)

        # ── external pipeline_ready topic ─────────────────────────────
        self.declare_parameter(
            'imu_pipeline_ready_topic', '/imu/pipeline_ready')

        img_in: str = self.get_parameter('image_topic_in').value
        imu_in: str = self.get_parameter('imu_topic_in').value
        img_out: str = self.get_parameter('image_topic_out').value
        imu_out: str = self.get_parameter('imu_topic_out').value
        pipeline_ready_topic: str = self.get_parameter(
            'imu_pipeline_ready_topic').value
        resampled_imu_topic_arg = str(
            self.get_parameter('resampled_imu_topic').value).strip()
        if resampled_imu_topic_arg:
            self._resampled_imu_topic = resampled_imu_topic_arg
        else:
            self._resampled_imu_topic = imu_out
        self._publish_batch_imu = bool(
            self.get_parameter('publish_batch_imu').value)
        self._batch_imu_topic = str(
            self.get_parameter('batch_imu_topic').value)
        self._requested_resampled_imu = bool(
            self.get_parameter('enable_resampled_imu').value)
        self._resampled_imu_rate_hz = float(
            self.get_parameter('resampled_imu_rate_hz').value)
        self._resampled_imu_latency_ms = float(
            self.get_parameter('resampled_imu_latency_ms').value)
        self._resampled_imu_max_gap_ms = float(
            self.get_parameter('resampled_imu_max_gap_ms').value)
        self._raw_hw_qos_depth = self._get_positive_int_param(
            'raw_hw_qos_depth', 1000)
        self._legacy_imu_qos_depth = self._get_positive_int_param(
            'legacy_imu_qos_depth', 50)
        self._executor_threads = self._get_positive_int_param(
            'executor_threads', 8)

        cfg = SyncConfig(
            cam_imu_time_offset=float(
                self.get_parameter('cam_imu_time_offset').value),
            steady_cam_to_imu_offset_sec=float(
                self.get_parameter('steady_cam_to_imu_offset_sec').value),
            imu_buffer_sec=float(
                self.get_parameter('imu_buffer_sec').value),
            enable_interpolation=bool(
                self.get_parameter('enable_interpolation').value),
            max_sync_wait_sec=float(
                self.get_parameter('max_sync_wait_ms').value) / 1000.0,
            max_interp_gap_sec=float(
                self.get_parameter('max_interp_gap_ms').value) / 1000.0,
            drop_frame_on_missing_imu=bool(
                self.get_parameter('drop_frame_on_missing_imu').value),
            warn_on_queue_backlog=bool(
                self.get_parameter('warn_on_queue_backlog').value),
            max_image_queue_size=int(
                self.get_parameter('max_image_queue_size').value),
            # state-machine parameters
            camera_startup_drop_sec=float(
                self.get_parameter('camera_startup_drop_sec').value),
            sync_wait_imu_ready_min_samples=int(
                self.get_parameter(
                    'sync_wait_imu_ready_min_samples').value),
            sync_wait_imu_ready_min_span_ms=float(
                self.get_parameter(
                    'sync_wait_imu_ready_min_span_ms').value),
            sync_wait_imu_ready_max_std_ms=float(
                self.get_parameter(
                    'sync_wait_imu_ready_max_std_ms').value),
            first_sync_safety_margin_sec=float(
                self.get_parameter(
                    'first_sync_safety_margin_ms').value) / 1000.0,
            first_sync_timeout_sec=float(
                self.get_parameter('first_sync_timeout_sec').value),
            first_sync_drop_limit=int(
                self.get_parameter('first_sync_drop_limit').value),
            sync_fail_lag_threshold_sec=float(
                self.get_parameter(
                    'sync_fail_lag_threshold_ms').value) / 1000.0,
            sync_fail_consecutive_limit=int(
                self.get_parameter(
                    'sync_fail_consecutive_limit').value),
            # Phase 1A
            deterministic_sync=bool(
                self.get_parameter('deterministic_sync').value),
            enable_header_rewrite=bool(
                self.get_parameter('enable_header_rewrite').value),
            min_stable_cam_frames=int(
                self.get_parameter('min_stable_cam_frames').value),
            cam_stable_max_std_ms=float(
                self.get_parameter('cam_stable_max_std_ms').value),
        )

        self._manager = SyncManager(
            cfg, make_imu=self._make_imu, clock=_time.monotonic)

        # ── Phase 1A: capture unified time offset ONCE at startup ─────
        self._deterministic_sync = cfg.deterministic_sync
        self._enable_header_rewrite = cfg.enable_header_rewrite
        self._enable_resampled_imu = (
            self._requested_resampled_imu and self._deterministic_sync)
        if self._deterministic_sync:
            ros_now_ns = self.get_clock().now().nanoseconds
            steady_now_ns = _time.monotonic_ns()
            self._manager.init_time_offset(ros_now_ns, steady_now_ns)

        # ── diagnostics setup ─────────────────────────────────────────
        self._debug_enable = bool(self.get_parameter('debug_enable').value)
        self._debug_expected_imu_rate_hz = float(
            self.get_parameter('debug_expected_imu_rate_hz').value)
        run_meta = build_run_meta(cfg)
        run_meta.update({
            'node': 'cam_imu_sync_node',
            'debug_enable': self._debug_enable,
            'debug_expected_imu_rate_hz':
                f'{self._debug_expected_imu_rate_hz:.3f}',
            'raw_hw_qos_depth': self._raw_hw_qos_depth,
            'legacy_imu_qos_depth': self._legacy_imu_qos_depth,
            'executor_threads': self._executor_threads,
        })
        self._diag = (
            DiagnosticsWriter(self.get_logger(), run_meta)
            if self._debug_enable else NullDiagnosticsWriter())

        self._proc_start_ns = _time.monotonic_ns()
        self._diag.run_start(self._proc_start_ns)

        # ── period / latency tracker ──────────────────────────────────
        self._cam_period_stats = OnlineStats()
        self._imu_period_stats = OnlineStats()
        self._sync_latency_stats = OnlineStats()
        self._last_cam_steady_ns: int = 0
        self._last_imu_steady_ns: int = 0
        self._first_cam_steady_ns: int = 0
        self._first_imu_steady_ns: int = 0

        # ── legacy diagnostics bookkeeping ────────────────────────────
        self._imu_recv_count: int = 0
        self._first_imu_mono: float = 0.0
        self._first_sync_mono: float = 0.0
        self._imu_freq_window_start: float = 0.0
        self._imu_freq_window_count: int = 0
        self._last_observed_imu_rate_hz: float = 0.0
        self._batch_imu_published: int = 0
        self._resampled_imu_published: int = 0
        self._resampled_gap_skip_count: int = 0
        self._resample_gap_skip_since_warn: int = 0
        self._last_resample_gap_warn_ns: int = 0
        self._resample_gap_warn_period_ns: int = 1_000_000_000
        self._resample_gap_warn_first_n: int = 3

        # ── state tracking for diagnostics ────────────────────────────
        self._last_reported_state = None
        self._resampler = None
        if self._enable_resampled_imu:
            self._resampler = FixedRateImuResampler(
                rate_hz=self._resampled_imu_rate_hz,
                latency_ms=self._resampled_imu_latency_ms,
                max_gap_ms=self._resampled_imu_max_gap_ms,
            )

        # ── startup banner ────────────────────────────────────────────
        self.get_logger().info(
            f'[STEADY DOMAIN] steady_offset = '
            f'{cfg.steady_cam_to_imu_offset_sec:.4f} s  '
            f'(target_steady = cam_steady + offset)')
        self.get_logger().info(
            f'  header_offset = {cfg.cam_imu_time_offset:.4f} s  '
            f'(legacy, observation only)')
        self.get_logger().info(
            f'interpolation = {"ON" if cfg.enable_interpolation else "OFF"}'
            f'  max_wait={cfg.max_sync_wait_sec*1e3:.0f} ms'
            f'  max_gap={cfg.max_interp_gap_sec*1e3:.0f} ms')
        self.get_logger().info(
            f'state_machine: cam_drop={cfg.camera_startup_drop_sec:.1f}s'
            f'  imu_ready_min={cfg.sync_wait_imu_ready_min_samples}'
            f'  fail_limit={cfg.sync_fail_consecutive_limit}'
            f'  first_sync_timeout={cfg.first_sync_timeout_sec:.1f}s'
            f'  first_sync_drop_limit={cfg.first_sync_drop_limit}')
        self.get_logger().info(f'  IN:  image={img_in}  imu={imu_in}')
        self.get_logger().info(
            f'  OUT: image={img_out}  resampled_imu={self._resampled_imu_topic}'
            f'  batch_imu={self._batch_imu_topic}')
        self.get_logger().info(
            f'  pipeline_ready_topic: {pipeline_ready_topic}')
        self.get_logger().info(
            f'  raw_hw_qos: RELIABLE keep_last={self._raw_hw_qos_depth}  '
            f'legacy_imu_qos: BEST_EFFORT keep_last='
            f'{self._legacy_imu_qos_depth}  '
            f'executor_threads={self._executor_threads}')
        if self._deterministic_sync:
            self.get_logger().info(
                f'  [Phase 1A] DETERMINISTIC SYNC ENABLED')
            self.get_logger().info(
                f'  [Phase 1A] ros_minus_steady_offset = '
                f'{self._manager.ros_minus_steady_offset:.6f} s')
            self.get_logger().info(
                f'  [Phase 1A] header_rewrite = '
                f'{self._enable_header_rewrite}')
        else:
            self.get_logger().info(
                f'  [LEGACY MODE] deterministic_sync = false')
        if not resampled_imu_topic_arg:
            self.get_logger().warn(
                'Parameter imu_topic_out is deprecated for fixed-rate IMU '
                f'output; using fallback topic {self._resampled_imu_topic}. '
                'Set resampled_imu_topic explicitly to remove this warning.')
        if self._requested_resampled_imu and not self._enable_resampled_imu:
            self.get_logger().warn(
                'Fixed-rate IMU output requires deterministic_sync=true; '
                '/sync/imu resampler disabled in legacy mode.')
        self.get_logger().info(
            f'  resampled_imu: enabled={self._enable_resampled_imu}  '
            f'rate={self._resampled_imu_rate_hz:.1f} Hz  '
            f'latency={self._resampled_imu_latency_ms:.1f} ms  '
            f'max_gap={self._resampled_imu_max_gap_ms:.1f} ms')
        self.get_logger().info(
            f'  batch_imu: enabled={self._publish_batch_imu}')
        if self._debug_enable:
            self.get_logger().info(
                '  DEBUG: ROS2 terminal/logger structured diagnostics enabled')
        else:
            self.get_logger().info('  DEBUG: disabled')

        # ── callback groups (for MultiThreadedExecutor) ──────────────
        imu_cg = rclpy.callback_groups.MutuallyExclusiveCallbackGroup()
        img_cg = rclpy.callback_groups.MutuallyExclusiveCallbackGroup()
        timer_cg = rclpy.callback_groups.MutuallyExclusiveCallbackGroup()
        diag_cg = rclpy.callback_groups.MutuallyExclusiveCallbackGroup()
        ready_cg = rclpy.callback_groups.MutuallyExclusiveCallbackGroup()
        imu_raw_cg = rclpy.callback_groups.MutuallyExclusiveCallbackGroup()
        resample_cg = rclpy.callback_groups.MutuallyExclusiveCallbackGroup()

        # ── QoS ──────────────────────────────────────────────────────
        reliable_qos = _reliable_qos(10)
        best_effort_qos = _best_effort_qos(self._legacy_imu_qos_depth)
        raw_hw_qos = _reliable_qos(self._raw_hw_qos_depth)

        # ── subscriptions ────────────────────────────────────────────
        self._img_sub = self.create_subscription(
            Image, img_in, self._on_image, reliable_qos,
            callback_group=img_cg)

        # Legacy IMU subscription: only when NOT in deterministic mode
        if not self._deterministic_sync:
            self._imu_sub = self.create_subscription(
                Imu, imu_in, self._on_imu, best_effort_qos,
                callback_group=imu_cg)
        else:
            self._imu_sub = None  # Phase 1A uses /imu/raw_hw instead

        # subscribe to pipeline_ready (方案 B)
        self._pipeline_ready_sub = self.create_subscription(
            Bool, pipeline_ready_topic, self._on_pipeline_ready,
            QoSProfile(
                depth=1,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.VOLATILE),
            callback_group=ready_cg)

        # ── Phase 1A: subscribe to /imu/raw_hw when deterministic ─────
        imu_raw_hw_topic: str = self.get_parameter(
            'imu_raw_hw_topic').value
        if self._deterministic_sync:
            # Lazy import: only needed in deterministic mode
            from yesense_interface.msg import ImuRawHw
            self._ImuRawHw = ImuRawHw  # store for callback
            self._imu_raw_sub = self.create_subscription(
                ImuRawHw, imu_raw_hw_topic, self._on_imu_raw,
                raw_hw_qos, callback_group=imu_raw_cg)
            self.get_logger().info(
                f'  [Phase 1A] subscribed to {imu_raw_hw_topic} '
                f'(RELIABLE keep_last={self._raw_hw_qos_depth})')
        else:
            self._imu_raw_sub = None

        # ── publishers ───────────────────────────────────────────────
        out_imu_qos = _best_effort_qos(50)
        self._img_pub = self.create_publisher(Image, img_out, 10)
        self._batch_imu_pub = self.create_publisher(
            Imu, self._batch_imu_topic, out_imu_qos)
        self._resampled_imu_pub = self.create_publisher(
            Imu, self._resampled_imu_topic, out_imu_qos)

        # ── drain timer (200 Hz → 5 ms) ─────────────────────────────
        self._drain_timer = self.create_timer(
            0.005, self._drain, callback_group=timer_cg)
        if self._enable_resampled_imu:
            self._resample_timer = self.create_timer(
                1.0 / self._resampled_imu_rate_hz,
                self._publish_resampled_imu,
                callback_group=resample_cg)
        else:
            self._resample_timer = None

        # ── diagnostics timer (1 Hz) ─────────────────────────────────
        self._diag_timer = (
            self.create_timer(
                1.0, self._publish_diagnostics, callback_group=diag_cg)
            if self._debug_enable else None)

        self.get_logger().info(
            'cam_imu_sync_node ready (steady-domain sync, '
            'external pipeline_ready)')

    def _get_positive_int_param(self, name: str, default: int) -> int:
        """Read an integer ROS parameter and clamp invalid values."""
        try:
            value = int(self.get_parameter(name).value)
        except (TypeError, ValueError):
            self.get_logger().warn(
                f'Parameter {name} is invalid; using {default}')
            return default
        if value < 1:
            self.get_logger().warn(
                f'Parameter {name}={value} is invalid; using 1')
            return 1
        return value

    # ================================================================
    # IMU factory (keeps sync_manager ROS-free)
    # ================================================================

    @staticmethod
    def _make_imu(
        sec: int,
        nanosec: int,
        frame_id: str,
        lin_acc: tuple[float, float, float],
        ang_vel: tuple[float, float, float],
    ) -> Imu:
        """Construct an ``Imu`` message from raw values."""
        out = Imu()
        out.header.stamp = TimeMsg(sec=sec, nanosec=nanosec)
        out.header.frame_id = frame_id
        out.linear_acceleration.x = lin_acc[0]
        out.linear_acceleration.y = lin_acc[1]
        out.linear_acceleration.z = lin_acc[2]
        out.angular_velocity.x = ang_vel[0]
        out.angular_velocity.y = ang_vel[1]
        out.angular_velocity.z = ang_vel[2]
        # Unknown covariance for interpolated point
        out.orientation_covariance[0] = -1.0
        out.linear_acceleration_covariance = [0.0] * 9
        out.angular_velocity_covariance = [0.0] * 9
        return out

    # ================================================================
    # callbacks — thin wrappers delegating to SyncManager
    # ================================================================

    def _on_pipeline_ready(self, msg: Bool) -> None:
        """Receive external IMU pipeline readiness signal (方案 B)."""
        self._manager.set_external_imu_ready(msg.data)

    def _on_imu_raw(self, msg) -> None:
        """Buffer incoming ImuRawHw message (Phase 1A).

        Uses ``msg.rx_steady_ns`` from the driver as the primary
        sync time.  Constructs an ``ImuRawSample`` and delegates
        to ``SyncManager.on_imu_raw()``.
        """
        local_steady_ns = _time.monotonic_ns()  # cross-check
        now = local_steady_ns / 1e9

        raw = ImuRawSample(
            tid=msg.tid,
            rx_steady_ns=msg.rx_steady_ns,
            rx_ros_ns=msg.rx_ros_ns,
            lin_acc=(msg.linear_acceleration.x,
                     msg.linear_acceleration.y,
                     msg.linear_acceleration.z),
            ang_vel=(msg.angular_velocity.x,
                     msg.angular_velocity.y,
                     msg.angular_velocity.z),
            orientation=(msg.orientation.x,
                         msg.orientation.y,
                         msg.orientation.z,
                         msg.orientation.w),
            frame_id=msg.header.frame_id,
            sample_timestamp=msg.sample_timestamp,
            data_ready_timestamp=msg.data_ready_timestamp,
            hw_ts_unit_sec=msg.hw_ts_unit_sec,
        )

        imu_id = self._manager.on_imu_raw(raw, now)

        if imu_id > 0:
            self._push_resample_sample_from_raw(msg)

            # ── first-sample milestone ──
            if self._first_imu_steady_ns == 0:
                self._first_imu_steady_ns = msg.rx_steady_ns
                self._diag.first_event('FIRST_IMU_RX', msg.rx_steady_ns)

            # ── inter-arrival period tracking ──
            if self._last_imu_steady_ns > 0:
                period_ms = (
                    msg.rx_steady_ns - self._last_imu_steady_ns) / 1e6
                self._imu_period_stats.update(period_ms)
            self._last_imu_steady_ns = msg.rx_steady_ns

            # ── CSV event ──
            self._diag.imu_rx(
                imu_id=imu_id,
                imu_header_ns=msg.rx_steady_ns,  # use steady as "header"
                steady_ns=msg.rx_steady_ns,
                queue_depth=self._manager.imu_buf_depth,
                ax=msg.linear_acceleration.x,
                ay=msg.linear_acceleration.y,
                az=msg.linear_acceleration.z,
                gx=msg.angular_velocity.x,
                gy=msg.angular_velocity.y,
                gz=msg.angular_velocity.z,
                extra=f'tid={msg.tid}',
            )

        # ── legacy IMU frequency tracking ──
        self._imu_recv_count += 1
        if self._first_imu_mono == 0.0:
            self._first_imu_mono = now
            self._imu_freq_window_start = now

        self._imu_freq_window_count += 1
        elapsed = now - self._imu_freq_window_start
        if elapsed >= 5.0:
            freq = self._imu_freq_window_count / elapsed
            self._last_observed_imu_rate_hz = freq
            self.get_logger().info(
                f'[IMU stats] freq={freq:.1f} Hz  '
                f'total_recv={self._imu_recv_count}  '
                f'tid_gaps={self._manager._tid_gap_count}')
            self._imu_freq_window_start = now
            self._imu_freq_window_count = 0

    def _on_imu(self, msg: Imu) -> None:
        """Buffer incoming IMU message — timestamp captured immediately."""
        steady_ns = _time.monotonic_ns()          # FIRST LINE!
        now = steady_ns / 1e9

        t = stamp2sec(msg.header.stamp)
        header_ns = _stamp_to_ns(msg.header.stamp)

        imu_id = self._manager.on_imu(
            t, msg, now, steady_ns=steady_ns)

        if imu_id > 0:
            # ── first-sample milestone ──
            if self._first_imu_steady_ns == 0:
                self._first_imu_steady_ns = steady_ns
                self._diag.first_event('FIRST_IMU_RX', steady_ns)

            # ── inter-arrival period tracking ──
            if self._last_imu_steady_ns > 0:
                period_ms = (steady_ns - self._last_imu_steady_ns) / 1e6
                self._imu_period_stats.update(period_ms)
            self._last_imu_steady_ns = steady_ns

            # ── CSV event ──
            self._diag.imu_rx(
                imu_id=imu_id,
                imu_header_ns=header_ns,
                steady_ns=steady_ns,
                queue_depth=self._manager.imu_buf_depth,
                ax=msg.linear_acceleration.x,
                ay=msg.linear_acceleration.y,
                az=msg.linear_acceleration.z,
                gx=msg.angular_velocity.x,
                gy=msg.angular_velocity.y,
                gz=msg.angular_velocity.z,
            )

        # ── legacy IMU frequency tracking ──
        self._imu_recv_count += 1
        if self._first_imu_mono == 0.0:
            self._first_imu_mono = now
            self._imu_freq_window_start = now

        self._imu_freq_window_count += 1
        elapsed = now - self._imu_freq_window_start
        if elapsed >= 5.0:
            freq = self._imu_freq_window_count / elapsed
            self._last_observed_imu_rate_hz = freq
            self.get_logger().info(
                f'[IMU stats] freq={freq:.1f} Hz  '
                f'total_recv={self._imu_recv_count}')
            self._imu_freq_window_start = now
            self._imu_freq_window_count = 0

    def _on_image(self, msg: Image) -> None:
        """Queue incoming camera frame — timestamp captured immediately."""
        steady_ns = _time.monotonic_ns()          # FIRST LINE!
        now = steady_ns / 1e9

        t = stamp2sec(msg.header.stamp)
        header_ns = _stamp_to_ns(msg.header.stamp)

        cam_frame_id = self._manager.on_image(
            t, msg, now,
            steady_ns=steady_ns, cam_header_ns=header_ns)

        if cam_frame_id > 0:
            # ── first-sample milestone ──
            if self._first_cam_steady_ns == 0:
                self._first_cam_steady_ns = steady_ns
                self._diag.first_event('FIRST_CAM_RX', steady_ns)

            # ── inter-arrival period tracking ──
            if self._last_cam_steady_ns > 0:
                period_ms = (steady_ns - self._last_cam_steady_ns) / 1e6
                self._cam_period_stats.update(period_ms)
            self._last_cam_steady_ns = steady_ns

            # ── CSV event ──
            self._diag.cam_rx(
                cam_frame_id=cam_frame_id,
                cam_header_ns=header_ns,
                steady_ns=steady_ns,
                queue_depth=self._manager.img_queue_depth,
            )

    def _push_resample_sample_from_raw(self, msg) -> None:
        """Store a raw IMU sample in the fixed-rate resampler buffer."""
        if not self._enable_resampled_imu or self._resampler is None:
            return

        self._resampler.push_sample(
            steady_ns=int(msg.rx_steady_ns),
            frame_id=msg.header.frame_id,
            lin_acc=(
                msg.linear_acceleration.x,
                msg.linear_acceleration.y,
                msg.linear_acceleration.z,
            ),
            ang_vel=(
                msg.angular_velocity.x,
                msg.angular_velocity.y,
                msg.angular_velocity.z,
            ),
        )

    def _publish_resampled_imu(self) -> None:
        """Publish one fixed-rate IMU sample per timer tick."""
        if (not self._enable_resampled_imu
                or self._resampler is None
                or not self._manager.offset_initialized):
            return

        outcome = self._resampler.poll()
        if outcome.kind == 'wait':
            return

        if outcome.kind == 'skip':
            self._resampled_gap_skip_count += 1
            self._resample_gap_skip_since_warn += 1
            now_ns = _time.monotonic_ns()
            should_warn = (
                self._resampled_gap_skip_count <= self._resample_gap_warn_first_n
                or now_ns - self._last_resample_gap_warn_ns
                >= self._resample_gap_warn_period_ns
            )
            if should_warn:
                suppressed = max(0, self._resample_gap_skip_since_warn - 1)
                suffix = (
                    f' (suppressed {suppressed} similar gaps)'
                    if suppressed else '')
                self.get_logger().warn(
                    f'resample IMU gap too large: {outcome.gap_ns / 1e6:.2f} '
                    f'ms at steady_ns={outcome.target_steady_ns}{suffix}')
                self._last_resample_gap_warn_ns = now_ns
                self._resample_gap_skip_since_warn = 0
            return

        if outcome.point is None:
            return

        ros_sec = self._manager.steady_ns_to_ros_sec(
            outcome.point.target_steady_ns)
        sec, nanosec = sec2stamp(ros_sec)
        out = self._make_imu(
            sec=sec,
            nanosec=nanosec,
            frame_id=outcome.point.frame_id,
            lin_acc=outcome.point.lin_acc,
            ang_vel=outcome.point.ang_vel,
        )
        self._resampled_imu_pub.publish(out)
        self._resampled_imu_published += 1
        if self._debug_enable:
            self._diag.resampled_imu(
                steady_ns=_time.monotonic_ns(),
                target_steady_ns=outcome.point.target_steady_ns,
                header_stamp_ns=sec * 1_000_000_000 + nanosec,
                source_kind=outcome.source_kind,
                before_steady_ns=outcome.before_steady_ns,
                after_steady_ns=outcome.after_steady_ns,
                alpha=outcome.alpha,
                gap_ns=outcome.gap_ns,
                ax=outcome.point.lin_acc[0],
                ay=outcome.point.lin_acc[1],
                az=outcome.point.lin_acc[2],
                gx=outcome.point.ang_vel[0],
                gy=outcome.point.ang_vel[1],
                gz=outcome.point.ang_vel[2],
            )

    def _drain(self) -> None:
        """Process queued images when enough IMU data is available."""
        now_ns = _time.monotonic_ns()
        now = now_ns / 1e9

        # Log state transitions
        current_state = self._manager.state
        if current_state != self._last_reported_state:
            self.get_logger().info(
                f'[sync state] {current_state.value}')
            self._diag.state_change(
                new_state=current_state.value,
                steady_ns=now_ns,
            )
            self._last_reported_state = current_state

        while True:
            batch = self._manager.try_sync(now)
            if batch is None:
                break

            decision_ns = _time.monotonic_ns()

            # ── Phase 1A: rewrite ALL headers BEFORE publishing ──────
            if (self._deterministic_sync
                    and self._enable_header_rewrite
                    and self._manager.offset_initialized):
                # Rewrite each IMU message's header
                for i, m in enumerate(batch.imu_msgs):
                    if i < len(batch.imu_steady_ns_list):
                        imu_sns = batch.imu_steady_ns_list[i]
                        if imu_sns > 0:
                            u_sec = self._manager.steady_ns_to_ros_sec(
                                imu_sns)
                            s2, ns2 = sec2stamp(u_sec)
                            m.header.stamp = TimeMsg(
                                sec=s2, nanosec=ns2)

                # Rewrite image header
                unified_cam_sec = self._manager.steady_ns_to_ros_sec(
                    batch.cam_steady_ns)
                s, ns = sec2stamp(unified_cam_sec)
                batch.image_msg.header.stamp = TimeMsg(sec=s, nanosec=ns)
            else:
                # Legacy: use header-domain alignment for image only
                s, ns = sec2stamp(batch.t_aligned)
                batch.image_msg.header.stamp = TimeMsg(sec=s, nanosec=ns)

            # ── Publish image and optional batch IMU diagnostics ────
            if self._publish_batch_imu:
                for m in batch.imu_msgs:
                    self._batch_imu_pub.publish(m)
                self._batch_imu_published += len(batch.imu_msgs)
            self._img_pub.publish(batch.image_msg)

            publish_ns = _time.monotonic_ns()

            # ── SYNC_OUT event ──
            # Steady-domain target (PRIMARY)
            target_align_steady_ns = int(batch.t_aligned_steady * 1e9)
            # Header-domain target (legacy observation)
            target_align_ns = int(batch.t_aligned * 1e9)
            applied_offset_ns = int(
                self._manager.cfg.cam_imu_time_offset * 1e9)
            applied_steady_offset_ns = int(
                self._manager.cfg.steady_cam_to_imu_offset_sec * 1e9)

            imu_first_id = batch.imu_ids[0] if batch.imu_ids else 0
            imu_last_id = batch.imu_ids[-1] if batch.imu_ids else 0
            imu_first_sns = (batch.imu_steady_ns_list[0]
                             if batch.imu_steady_ns_list else 0)
            imu_last_sns = (batch.imu_steady_ns_list[-1]
                            if batch.imu_steady_ns_list else 0)

            cam_minus_imu_last_ns = (
                batch.cam_steady_ns - imu_last_sns
                if imu_last_sns else 0)

            self._diag.sync_out(
                sync_frame_id=self._manager.stats.synced_frames,
                cam_frame_id=batch.cam_frame_id,
                cam_header_ns=batch.cam_header_ns,
                cam_steady_ns=batch.cam_steady_ns,
                sync_decision_steady_ns=decision_ns,
                publish_steady_ns=publish_ns,
                imu_first_id=imu_first_id,
                imu_last_id=imu_last_id,
                imu_count=len(batch.imu_msgs),
                imu_first_steady_ns=imu_first_sns,
                imu_last_steady_ns=imu_last_sns,
                interp_used=batch.interp_used,
                target_align_ns=target_align_ns,
                applied_offset_ns=applied_offset_ns,
                cam_minus_imu_last_ns=cam_minus_imu_last_ns,
                target_align_steady_ns=target_align_steady_ns,
                applied_steady_offset_ns=applied_steady_offset_ns,
            )

            # ── sync-latency tracking ──
            if batch.cam_steady_ns > 0:
                latency_ms = (decision_ns - batch.cam_steady_ns) / 1e6
                self._sync_latency_stats.update(latency_ms)

            # first-sync diagnostics
            if self._first_sync_mono == 0.0:
                self._first_sync_mono = now
                if self._first_imu_mono > 0.0:
                    startup_delay = now - self._first_imu_mono
                    self.get_logger().info(
                        f'[sync] first frame synced! '
                        f'startup_delay={startup_delay:.3f} s')

        # Flush manager log messages to ROS logger
        self._flush_manager_logs()

    def _flush_manager_logs(self) -> None:
        """Emit any pending log messages from the manager."""
        for entry in self._manager.drain_logs():
            if entry.level == 'warn':
                self.get_logger().warn(entry.message)
            elif entry.level == 'error':
                self.get_logger().error(entry.message)
            else:
                self.get_logger().info(entry.message)

    def _publish_diagnostics(self) -> None:
        """Periodic stats output (§14 – every 1 second)."""
        s = self._manager.stats
        state = self._manager.state.value
        input_imu_rate_hz = _input_imu_rate_hz(
            self._last_observed_imu_rate_hz,
            self._imu_period_stats.mean,
        )
        self.get_logger().info(
            f'[sync stats] state={state}  synced={s.synced_frames}  '
            f'dropped={s.dropped_frames}  '
            f'interp={s.interp_count}  '
            f'sync_batch_imu={s.total_imu_published}  '
            f'batch_imu_pub={self._batch_imu_published}  '
            f'resampled_imu_pub={self._resampled_imu_published}  '
            f'resample_gap_skip={self._resampled_gap_skip_count}  '
            f'input_imu_rate_hz={input_imu_rate_hz:.1f}  '
            f'input_imu_period_ms={self._imu_period_stats.mean:.3f}  '
            f'input_imu_period_std_ms={self._imu_period_stats.std:.3f}  '
            f'timeout={s.sync_wait_timeout_count}  '
            f'ts_anomaly={s.timestamp_anomaly_count}  '
            f'q_overflow={s.queue_overflow_count}  '
            f'resets={s.reset_count}  '
            f'rearms={s.rearm_count}  '
            f'sync_fails={s.sync_fail_count}  '
            f'cam_drops={s.camera_startup_drops}')
        self._diag.summary_1hz(
            steady_ns=_time.monotonic_ns(),
            state=state,
            synced_frames=s.synced_frames,
            dropped_frames=s.dropped_frames,
            interp_count=s.interp_count,
            sync_batch_imu=s.total_imu_published,
            batch_imu_pub=self._batch_imu_published,
            resampled_imu_pub=self._resampled_imu_published,
            resample_gap_skip=self._resampled_gap_skip_count,
            input_imu_rate_hz=f'{input_imu_rate_hz:.3f}',
            observed_sync_imu_rate_hz=
                f'{input_imu_rate_hz:.3f}',
            imu_mean_period_ms=f'{self._imu_period_stats.mean:.3f}',
            imu_period_std_ms=f'{self._imu_period_stats.std:.3f}',
            cam_mean_period_ms=f'{self._cam_period_stats.mean:.3f}',
            sync_fails=s.sync_fail_count,
            resets=s.reset_count,
        )

    # ================================================================
    # shutdown — write summary and close CSV
    # ================================================================

    def _write_run_summary(self) -> None:
        """Compute and print the end-of-run summary."""
        if not self._debug_enable:
            return
        s = self._manager.stats
        cam_count = (self._cam_period_stats.n + 1
                     if self._cam_period_stats.n > 0 else 0)
        imu_count = (self._imu_period_stats.n + 1
                     if self._imu_period_stats.n > 0 else 0)
        input_imu_rate_hz = _input_imu_rate_hz(
            self._last_observed_imu_rate_hz,
            self._imu_period_stats.mean,
        )

        summary = {
            'cam_frames': cam_count,
            'imu_frames': imu_count,
            'sync_frames': s.synced_frames,
            'dropped_frames': s.dropped_frames,
            'cam_mean_period_ms': f'{self._cam_period_stats.mean:.3f}',
            'input_imu_rate_hz': f'{input_imu_rate_hz:.3f}',
            'imu_mean_period_ms': f'{self._imu_period_stats.mean:.3f}',
            'imu_period_std_ms': f'{self._imu_period_stats.std:.3f}',
            'cam_to_sync_mean_ms':
                f'{self._sync_latency_stats.mean:.3f}',
            'cam_to_sync_std_ms':
                f'{self._sync_latency_stats.std:.3f}',
            'first_steady_cam_ns': self._first_cam_steady_ns,
            'first_steady_imu_ns': self._first_imu_steady_ns,
            'estimated_cam_imu_offset_ms': 'N/A',
            'sync_batch_imu_count': s.total_imu_published,
            'published_batch_imu_count': self._batch_imu_published,
            'published_resampled_imu_count': self._resampled_imu_published,
            'resampled_gap_skip_count': self._resampled_gap_skip_count,
            'interp_count': s.interp_count,
            'timeout_count': s.sync_wait_timeout_count,
            'ts_anomaly_count': s.timestamp_anomaly_count,
            'queue_overflow_count': s.queue_overflow_count,
            'reset_count': s.reset_count,
            # state-machine stats
            'state_transitions': s.state_transitions,
            'camera_startup_drops': s.camera_startup_drops,
            'sync_fail_count': s.sync_fail_count,
            'rearm_count': s.rearm_count,
            # NEW: steady-domain config
            'steady_cam_to_imu_offset_sec':
                f'{self._manager.cfg.steady_cam_to_imu_offset_sec:.6f}',
            'first_sync_timeout_sec':
                f'{self._manager.cfg.first_sync_timeout_sec:.1f}',
            'first_sync_drop_limit':
                self._manager.cfg.first_sync_drop_limit,
            # Phase 1A
            'deterministic_sync': self._deterministic_sync,
            'enable_header_rewrite': self._enable_header_rewrite,
            'enable_resampled_imu': self._enable_resampled_imu,
            'resampled_imu_topic': self._resampled_imu_topic,
            'resampled_imu_rate_hz': f'{self._resampled_imu_rate_hz:.3f}',
            'resampled_imu_latency_ms':
                f'{self._resampled_imu_latency_ms:.3f}',
            'resampled_imu_max_gap_ms':
                f'{self._resampled_imu_max_gap_ms:.3f}',
            'publish_batch_imu': self._publish_batch_imu,
            'batch_imu_topic': self._batch_imu_topic,
            'ros_minus_steady_offset':
                f'{self._manager.ros_minus_steady_offset:.9f}',
            'tid_gap_count': self._manager._tid_gap_count,
            'tid_reorder_count': self._manager._tid_reorder_count,
        }

        self._diag.write_summary(summary)
        self.get_logger().info(
            '[SUMMARY] printed to ROS2 logger')

    def destroy_node(self) -> None:
        """Write summary and close diagnostics before shutdown."""
        try:
            self._write_run_summary()
            self._diag.close()
        except Exception as e:
            self.get_logger().error(f'Failed to write summary: {e}')
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    executor = None
    try:
        node = CamImuSyncNode()
        executor_threads = node._executor_threads
        # MultiThreadedExecutor so IMU/image/timer run in parallel.
        executor = rclpy.executors.MultiThreadedExecutor(
            num_threads=executor_threads)
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if executor is not None:
            executor.shutdown()
        if node is not None:
            node.destroy_node()
        _safe_rclpy_shutdown()


if __name__ == '__main__':
    main()
