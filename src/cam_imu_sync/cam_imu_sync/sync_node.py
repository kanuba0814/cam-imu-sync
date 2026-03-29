#!/usr/bin/env python3
# Copyright 2026 gxxl. MIT License.
"""Camera-IMU time-offset synchronisation node with linear interpolation.

Subscribes to raw camera and IMU topics, compensates for the known
Kalibr-calibrated time offset  ``t_imu = t_cam + offset``,  and
republishes both streams on synchronised output topics.

Strategy
--------
1. Buffer incoming IMU messages in a time-sorted deque.
2. Queue incoming camera frames.
3. A 200 Hz timer ("drain") checks the oldest queued camera frame:
   - compute ``t_aligned = t_cam + offset``
   - if the latest buffered IMU timestamp >= t_aligned, we have enough data
   - collect all IMU messages in (prev_aligned, t_aligned]
   - **linearly interpolate** a synthetic IMU sample at exactly t_aligned
     using the last IMU before and first IMU after the boundary
   - publish the IMU batch (originals + interpolated boundary point)
   - publish the camera frame re-stamped to ``t_aligned``

This guarantees that for every published image, the IMU stream ends
exactly at the image timestamp, which is what ORB-SLAM3 expects for
optimal pre-integration.
"""

import collections
import copy
import threading
import time as _time

import rclpy
import rclpy.callback_groups
import rclpy.executors
from builtin_interfaces.msg import Time as TimeMsg
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image, Imu


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

        self._offset: float = (
            self.get_parameter('cam_imu_time_offset').value)
        img_in: str = self.get_parameter('image_topic_in').value
        imu_in: str = self.get_parameter('imu_topic_in').value
        img_out: str = self.get_parameter('image_topic_out').value
        imu_out: str = self.get_parameter('imu_topic_out').value
        self._buf_sec: float = self.get_parameter('imu_buffer_sec').value
        self._enable_interp: bool = (
            self.get_parameter('enable_interpolation').value)

        self.get_logger().info(
            f'offset = {self._offset:.4f} s  '
            f'(t_imu = t_cam + {self._offset:.4f})')
        self.get_logger().info(
            f'interpolation = {"ON" if self._enable_interp else "OFF"}')
        self.get_logger().info(f'  IN:  image={img_in}  imu={imu_in}')
        self.get_logger().info(f'  OUT: image={img_out} imu={imu_out}')

        # ── shared state ──────────────────────────────────────────────
        # deque of (float timestamp_sec, Imu msg)
        self._imu_buf: collections.deque = collections.deque()
        # deque of (float timestamp_sec, Image msg)
        self._img_queue: collections.deque = collections.deque()
        self._lock = threading.Lock()
        self._prev_aligned_t: float = 0.0
        self._sync_count: int = 0

        # ── diagnostics ──────────────────────────────────────────────
        self._interp_count: int = 0       # times interpolation was used
        self._no_interp_count: int = 0    # times interp was skipped
        self._total_imu_published: int = 0
        self._first_imu_t: float = 0.0
        self._first_sync_t: float = 0.0
        self._imu_recv_count: int = 0
        self._imu_freq_window_start: float = 0.0
        self._imu_freq_window_count: int = 0

        # ── callback groups (for MultiThreadedExecutor) ───────────────
        imu_cg = rclpy.callback_groups.MutuallyExclusiveCallbackGroup()
        img_cg = rclpy.callback_groups.MutuallyExclusiveCallbackGroup()
        timer_cg = rclpy.callback_groups.MutuallyExclusiveCallbackGroup()

        # ── QoS ───────────────────────────────────────────────────────
        reliable_qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE)
        best_effort_qos = QoSProfile(
            depth=50,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE)

        # ── subscriptions ─────────────────────────────────────────────
        self._img_sub = self.create_subscription(
            Image, img_in, self._on_image, reliable_qos,
            callback_group=img_cg)
        self._imu_sub = self.create_subscription(
            Imu, imu_in, self._on_imu, best_effort_qos,
            callback_group=imu_cg)

        # ── publishers ────────────────────────────────────────────────
        # Output IMU as BEST_EFFORT to match ORB-SLAM3 subscriber QoS
        out_imu_qos = QoSProfile(
            depth=50,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE)
        self._img_pub = self.create_publisher(Image, img_out, 10)
        self._imu_pub = self.create_publisher(Imu, imu_out, out_imu_qos)

        # ── drain timer (200 Hz → 5 ms) ──────────────────────────────
        self._timer = self.create_timer(
            0.005, self._drain, callback_group=timer_cg)

        self.get_logger().info('cam_imu_sync_node ready (interpolation mode)')

    # ================================================================
    # helpers
    # ================================================================

    @staticmethod
    def _stamp2sec(stamp) -> float:
        """Convert builtin_interfaces/Time to seconds."""
        return stamp.sec + stamp.nanosec * 1e-9

    @staticmethod
    def _sec2stamp(t: float) -> TimeMsg:
        """Convert seconds to builtin_interfaces/Time."""
        sec = int(t)
        nsec = int(round((t - sec) * 1e9))
        if nsec >= 1_000_000_000:
            sec += 1
            nsec -= 1_000_000_000
        return TimeMsg(sec=sec, nanosec=nsec)

    @staticmethod
    def _lerp_imu(imu_a: Imu, imu_b: Imu, t_target: float) -> Imu:
        """Linearly interpolate two IMU messages to t_target.

        Interpolates both linear_acceleration and angular_velocity.
        The result inherits frame_id from imu_a.

        Parameters
        ----------
        imu_a : Imu
            IMU sample before t_target.
        imu_b : Imu
            IMU sample after t_target.
        t_target : float
            Target time in seconds.

        Returns
        -------
        Imu
            Synthetic IMU message at exactly t_target.
        """
        t0 = imu_a.header.stamp.sec + imu_a.header.stamp.nanosec * 1e-9
        t1 = imu_b.header.stamp.sec + imu_b.header.stamp.nanosec * 1e-9

        dt = t1 - t0
        if abs(dt) < 1e-9:
            out = copy.deepcopy(imu_a)
            out.header.stamp = CamImuSyncNode._sec2stamp(t_target)
            return out

        alpha = (t_target - t0) / dt
        alpha = max(0.0, min(1.0, alpha))
        beta = 1.0 - alpha

        out = Imu()
        out.header.stamp = CamImuSyncNode._sec2stamp(t_target)
        out.header.frame_id = imu_a.header.frame_id

        # Interpolate linear acceleration
        out.linear_acceleration.x = (
            beta * imu_a.linear_acceleration.x
            + alpha * imu_b.linear_acceleration.x)
        out.linear_acceleration.y = (
            beta * imu_a.linear_acceleration.y
            + alpha * imu_b.linear_acceleration.y)
        out.linear_acceleration.z = (
            beta * imu_a.linear_acceleration.z
            + alpha * imu_b.linear_acceleration.z)

        # Interpolate angular velocity
        out.angular_velocity.x = (
            beta * imu_a.angular_velocity.x
            + alpha * imu_b.angular_velocity.x)
        out.angular_velocity.y = (
            beta * imu_a.angular_velocity.y
            + alpha * imu_b.angular_velocity.y)
        out.angular_velocity.z = (
            beta * imu_a.angular_velocity.z
            + alpha * imu_b.angular_velocity.z)

        # Zero out covariance (unknown for interpolated point)
        out.orientation_covariance[0] = -1.0
        out.linear_acceleration_covariance = [0.0] * 9
        out.angular_velocity_covariance = [0.0] * 9

        return out

    # ================================================================
    # callbacks
    # ================================================================

    def _on_imu(self, msg: Imu) -> None:
        """Buffer incoming IMU message."""
        t = self._stamp2sec(msg.header.stamp)
        with self._lock:
            self._imu_buf.append((t, msg))
            # trim stale data
            cutoff = t - self._buf_sec
            while self._imu_buf and self._imu_buf[0][0] < cutoff:
                self._imu_buf.popleft()

            # diagnostics: IMU receive counting
            self._imu_recv_count += 1
            if self._first_imu_t == 0.0:
                self._first_imu_t = _time.monotonic()
                self._imu_freq_window_start = _time.monotonic()

            # IMU frequency measurement (every 5 seconds)
            self._imu_freq_window_count += 1
            now_mono = _time.monotonic()
            elapsed = now_mono - self._imu_freq_window_start
            if elapsed >= 5.0:
                freq = self._imu_freq_window_count / elapsed
                buf_len = len(self._imu_buf)
                self.get_logger().info(
                    f'[IMU stats] freq={freq:.1f} Hz  '
                    f'buf_size={buf_len}  '
                    f'total_recv={self._imu_recv_count}')
                self._imu_freq_window_start = now_mono
                self._imu_freq_window_count = 0

    def _on_image(self, msg: Image) -> None:
        """Queue incoming camera frame."""
        t = self._stamp2sec(msg.header.stamp)
        with self._lock:
            self._img_queue.append((t, msg))

    def _drain(self) -> None:
        """Process queued images when enough IMU data is available.

        For each camera frame at t_aligned = t_cam + offset:
        1. Collect all IMU samples with timestamps in (prev_aligned, t_aligned]
        2. If interpolation is enabled and there exists an IMU sample after
           t_aligned, interpolate a boundary point at exactly t_aligned
        3. Publish IMU batch then the image
        """
        with self._lock:
            while self._img_queue:
                t_cam, img_msg = self._img_queue[0]
                t_aligned = t_cam + self._offset

                # need IMU data covering past t_aligned
                if not self._imu_buf:
                    break
                latest_imu_t = self._imu_buf[-1][0]
                if latest_imu_t < t_aligned:
                    break  # not enough IMU data yet → wait

                # enough data: pop this image
                self._img_queue.popleft()

                # ── collect IMU in (prev_aligned, t_aligned] ──────────
                imu_batch: list[Imu] = []
                imu_before_boundary: Imu | None = None  # last IMU <= t_aligned
                imu_after_boundary: Imu | None = None   # first IMU > t_aligned

                # We need to scan the buffer without destroying data
                # that future frames might need. Use index-based scan.
                consume_up_to = 0  # how many to pop from front

                for idx, (t_imu, imu_msg) in enumerate(self._imu_buf):
                    if t_imu <= self._prev_aligned_t:
                        # already consumed by previous frame
                        consume_up_to = idx + 1
                        continue

                    if t_imu <= t_aligned:
                        imu_batch.append(imu_msg)
                        imu_before_boundary = imu_msg
                        consume_up_to = idx + 1
                    else:
                        # first IMU after t_aligned
                        imu_after_boundary = imu_msg
                        break

                # Pop consumed entries from the deque
                for _ in range(consume_up_to):
                    self._imu_buf.popleft()

                # ── interpolation at t_aligned boundary ───────────────
                if (self._enable_interp
                        and imu_before_boundary is not None
                        and imu_after_boundary is not None):
                    t_before = self._stamp2sec(
                        imu_before_boundary.header.stamp)
                    # Only interpolate if the boundary IMU is not already
                    # at exactly t_aligned (within 0.1ms tolerance)
                    if abs(t_before - t_aligned) > 1e-4:
                        interp_imu = self._lerp_imu(
                            imu_before_boundary,
                            imu_after_boundary,
                            t_aligned)
                        imu_batch.append(interp_imu)
                        self._interp_count += 1
                    else:
                        self._no_interp_count += 1
                else:
                    self._no_interp_count += 1

                self._prev_aligned_t = t_aligned

                # ── publish ───────────────────────────────────────────
                # Publish IMU batch first (so downstream has them before
                # the image triggers processing)
                for m in imu_batch:
                    self._imu_pub.publish(m)
                self._total_imu_published += len(imu_batch)

                # Publish image with aligned timestamp
                img_msg.header.stamp = self._sec2stamp(t_aligned)
                self._img_pub.publish(img_msg)

                # ── diagnostics ───────────────────────────────────────
                self._sync_count += 1
                if self._first_sync_t == 0.0:
                    self._first_sync_t = _time.monotonic()
                    startup_delay = (
                        self._first_sync_t - self._first_imu_t)
                    self.get_logger().info(
                        f'[sync] first frame synced! '
                        f'startup_delay={startup_delay:.3f} s')

                if self._sync_count % 60 == 0:  # ~2 s at 30 fps
                    self.get_logger().info(
                        f'[sync #{self._sync_count}] '
                        f't={t_aligned:.3f}  '
                        f'imu_n={len(imu_batch)}  '
                        f'img_q={len(self._img_queue)}  '
                        f'imu_buf={len(self._imu_buf)}  '
                        f'interp={self._interp_count}/'
                        f'{self._interp_count + self._no_interp_count}  '
                        f'total_imu={self._total_imu_published}')


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
