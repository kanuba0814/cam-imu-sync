#!/usr/bin/env python3
# Copyright 2026 gxxl. MIT License.
"""Camera-IMU time-offset synchronisation node.

Subscribes to raw camera and IMU topics, compensates for the known
Kalibr-calibrated time offset  ``t_imu = t_cam + offset``,  and
republishes both streams on synchronised output topics.

Strategy
--------
1. Buffer incoming IMU messages in a time-sorted deque.
2. Queue incoming camera frames.
3. A 200 Hz timer ("drain") checks the oldest queued camera frame:
   - compute ``t_aligned = t_cam + offset``
   - if the latest buffered IMU timestamp ≥ t_aligned, we have enough data
   - pop all IMU messages in (prev_aligned, t_aligned]
   - publish those IMU messages (original timestamps)
   - publish the camera frame re-stamped to ``t_aligned``

This guarantees that for every published image, all corresponding IMU
samples have already been published.  Downstream consumers (e.g.
ORB-SLAM3) can consume the two topics directly without any extra
time-offset logic.
"""

import collections
import threading

import rclpy
import rclpy.callback_groups
import rclpy.executors
from builtin_interfaces.msg import Time as TimeMsg
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image, Imu


class CamImuSyncNode(Node):
    """Delay-synchronise camera and IMU by a fixed time offset."""

    def __init__(self) -> None:
        super().__init__('cam_imu_sync_node')

        # ── parameters ────────────────────────────────────────────────
        self.declare_parameter('cam_imu_time_offset', 0.2745)
        self.declare_parameter('image_topic_in', '/image_raw')
        self.declare_parameter('imu_topic_in', '/imu/data_raw')
        self.declare_parameter('image_topic_out', '/sync/image_raw')
        self.declare_parameter('imu_topic_out', '/sync/imu')
        self.declare_parameter('imu_buffer_sec', 3.0)

        self._offset: float = (
            self.get_parameter('cam_imu_time_offset').value)
        img_in: str = self.get_parameter('image_topic_in').value
        imu_in: str = self.get_parameter('imu_topic_in').value
        img_out: str = self.get_parameter('image_topic_out').value
        imu_out: str = self.get_parameter('imu_topic_out').value
        self._buf_sec: float = self.get_parameter('imu_buffer_sec').value

        self.get_logger().info(
            f'offset = {self._offset:.4f} s  '
            f'(t_imu = t_cam + {self._offset:.4f})')
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
        self._img_pub = self.create_publisher(Image, img_out, 10)
        self._imu_pub = self.create_publisher(Imu, imu_out, 50)

        # ── drain timer (200 Hz → 5 ms) ──────────────────────────────
        self._timer = self.create_timer(
            0.005, self._drain, callback_group=timer_cg)

        self.get_logger().info('cam_imu_sync_node ready')

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

    def _on_image(self, msg: Image) -> None:
        """Queue incoming camera frame."""
        t = self._stamp2sec(msg.header.stamp)
        with self._lock:
            self._img_queue.append((t, msg))

    def _drain(self) -> None:
        """Process queued images when enough IMU data is available."""
        with self._lock:
            while self._img_queue:
                t_cam, img_msg = self._img_queue[0]
                t_aligned = t_cam + self._offset

                # need IMU data covering up to t_aligned
                if not self._imu_buf:
                    break
                latest_imu_t = self._imu_buf[-1][0]
                if latest_imu_t < t_aligned:
                    break  # not enough IMU data yet → wait

                # enough data: pop this image
                self._img_queue.popleft()

                # collect IMU in (prev_aligned, t_aligned]
                imu_batch: list[Imu] = []
                while self._imu_buf:
                    t_imu, imu_msg = self._imu_buf[0]
                    if t_imu <= self._prev_aligned_t:
                        self._imu_buf.popleft()  # already consumed
                        continue
                    if t_imu <= t_aligned:
                        imu_batch.append(imu_msg)
                        self._imu_buf.popleft()
                    else:
                        break  # rest belongs to future frames

                self._prev_aligned_t = t_aligned

                # publish IMU batch first (so downstream has them before
                # the image triggers processing)
                for m in imu_batch:
                    self._imu_pub.publish(m)

                # publish image with aligned timestamp
                img_msg.header.stamp = self._sec2stamp(t_aligned)
                self._img_pub.publish(img_msg)

                self._sync_count += 1
                if self._sync_count % 60 == 1:  # ~2 s at 30 fps
                    self.get_logger().info(
                        f'[sync #{self._sync_count}] '
                        f't={t_aligned:.3f}  '
                        f'imu_n={len(imu_batch)}  '
                        f'img_q={len(self._img_queue)}  '
                        f'imu_buf={len(self._imu_buf)}')


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
