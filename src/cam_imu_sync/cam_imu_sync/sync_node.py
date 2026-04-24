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
All events are written to a per-run CSV file via :class:`DiagnosticsWriter`.
Timestamps use ``time.monotonic_ns()`` for nanosecond-precision monotonic
clock analysis.  Each run produces::

    {log_dir}/{run_id}/meta.txt
    {log_dir}/{run_id}/events.csv
    {log_dir}/{run_id}/summary.txt
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

from .diagnostics import DiagnosticsWriter, OnlineStats, build_run_meta
from .models import ImuRawSample, SyncConfig
from .sync_manager import SyncManager, stamp2sec, sec2stamp


def _stamp_to_ns(stamp) -> int:
    """Convert a ROS ``builtin_interfaces/Time`` to nanoseconds."""
    return stamp.sec * 1_000_000_000 + stamp.nanosec


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
        # §12 / §13 parameters
        self.declare_parameter('max_sync_wait_ms', 100.0)
        self.declare_parameter('max_interp_gap_ms', 10.0)
        self.declare_parameter('drop_frame_on_missing_imu', True)
        self.declare_parameter('warn_on_queue_backlog', True)
        self.declare_parameter('max_image_queue_size', 20)
        # diagnostics parameters
        self.declare_parameter('run_id', '')
        self.declare_parameter(
            'log_dir',
            '/home/gxxl/slam_ws_v2/extra_ws/logs/cam_imu_sync')

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
        if self._deterministic_sync:
            ros_now_ns = self.get_clock().now().nanoseconds
            steady_now_ns = _time.monotonic_ns()
            self._manager.init_time_offset(ros_now_ns, steady_now_ns)

        # ── diagnostics setup ─────────────────────────────────────────
        run_id = self.get_parameter('run_id').value
        if not run_id:
            run_id = _time.strftime('%Y-%m-%dT%H-%M-%S')
        log_dir = self.get_parameter('log_dir').value

        run_meta = build_run_meta(run_id, cfg)
        self._diag = DiagnosticsWriter(run_id, log_dir, run_meta)

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

        # ── state tracking for diagnostics ────────────────────────────
        self._last_reported_state = None

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
        self.get_logger().info(f'  OUT: image={img_out} imu={imu_out}')
        self.get_logger().info(
            f'  pipeline_ready_topic: {pipeline_ready_topic}')
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
        self.get_logger().info(
            f'  DIAG: {self._diag.run_dir}/events.csv')

        # ── callback groups (for MultiThreadedExecutor) ──────────────
        imu_cg = rclpy.callback_groups.MutuallyExclusiveCallbackGroup()
        img_cg = rclpy.callback_groups.MutuallyExclusiveCallbackGroup()
        timer_cg = rclpy.callback_groups.MutuallyExclusiveCallbackGroup()
        diag_cg = rclpy.callback_groups.MutuallyExclusiveCallbackGroup()
        ready_cg = rclpy.callback_groups.MutuallyExclusiveCallbackGroup()
        imu_raw_cg = rclpy.callback_groups.MutuallyExclusiveCallbackGroup()

        # ── QoS ──────────────────────────────────────────────────────
        reliable_qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE)
        best_effort_qos = QoSProfile(
            depth=50,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE)

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
                best_effort_qos, callback_group=imu_raw_cg)
            self.get_logger().info(
                f'  [Phase 1A] subscribed to {imu_raw_hw_topic}')
        else:
            self._imu_raw_sub = None

        # ── publishers ───────────────────────────────────────────────
        out_imu_qos = QoSProfile(
            depth=50,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE)
        self._img_pub = self.create_publisher(Image, img_out, 10)
        self._imu_pub = self.create_publisher(Imu, imu_out, out_imu_qos)

        # ── drain timer (200 Hz → 5 ms) ─────────────────────────────
        self._drain_timer = self.create_timer(
            0.005, self._drain, callback_group=timer_cg)

        # ── diagnostics timer (1 Hz) ─────────────────────────────────
        self._diag_timer = self.create_timer(
            1.0, self._publish_diagnostics, callback_group=diag_cg)

        self.get_logger().info(
            'cam_imu_sync_node ready (steady-domain sync, '
            'external pipeline_ready)')

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

            # ── Publish (headers already correct) ────────────────────
            for m in batch.imu_msgs:
                self._imu_pub.publish(m)
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
        self.get_logger().info(
            f'[sync stats] state={state}  synced={s.synced_frames}  '
            f'dropped={s.dropped_frames}  '
            f'interp={s.interp_count}  '
            f'imu_pub={s.total_imu_published}  '
            f'timeout={s.sync_wait_timeout_count}  '
            f'ts_anomaly={s.timestamp_anomaly_count}  '
            f'q_overflow={s.queue_overflow_count}  '
            f'resets={s.reset_count}  '
            f'rearms={s.rearm_count}  '
            f'sync_fails={s.sync_fail_count}  '
            f'cam_drops={s.camera_startup_drops}')

    # ================================================================
    # shutdown — write summary and close CSV
    # ================================================================

    def _write_run_summary(self) -> None:
        """Compute and write the end-of-run summary.txt."""
        s = self._manager.stats
        cam_count = (self._cam_period_stats.n + 1
                     if self._cam_period_stats.n > 0 else 0)
        imu_count = (self._imu_period_stats.n + 1
                     if self._imu_period_stats.n > 0 else 0)

        summary = {
            'run_id': self._diag.run_id,
            'cam_frames': cam_count,
            'imu_frames': imu_count,
            'sync_frames': s.synced_frames,
            'dropped_frames': s.dropped_frames,
            'cam_mean_period_ms': f'{self._cam_period_stats.mean:.3f}',
            'imu_mean_period_ms': f'{self._imu_period_stats.mean:.3f}',
            'imu_period_std_ms': f'{self._imu_period_stats.std:.3f}',
            'cam_to_sync_mean_ms':
                f'{self._sync_latency_stats.mean:.3f}',
            'cam_to_sync_std_ms':
                f'{self._sync_latency_stats.std:.3f}',
            'first_steady_cam_ns': self._first_cam_steady_ns,
            'first_steady_imu_ns': self._first_imu_steady_ns,
            'estimated_cam_imu_offset_ms': 'N/A',
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
            'ros_minus_steady_offset':
                f'{self._manager.ros_minus_steady_offset:.9f}',
            'tid_gap_count': self._manager._tid_gap_count,
            'tid_reorder_count': self._manager._tid_reorder_count,
        }

        self._diag.write_summary(summary)
        self.get_logger().info(
            f'[SUMMARY] written to {self._diag.run_dir}/summary.txt')

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
    node = CamImuSyncNode()

    # MultiThreadedExecutor so IMU/image/timer run in parallel
    executor = rclpy.executors.MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
