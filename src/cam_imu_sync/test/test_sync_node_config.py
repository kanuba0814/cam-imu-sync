#!/usr/bin/env python3
# Copyright 2026 gxxl. MIT License.
"""Configuration helper tests for the ROS sync node wrapper."""

from __future__ import annotations

import rclpy
from rclpy.qos import ReliabilityPolicy

from cam_imu_sync.sync_node import (
    _best_effort_qos,
    _reliable_qos,
    _safe_rclpy_shutdown,
)


def test_raw_hw_qos_default_is_reliable_depth_1000():
    qos = _reliable_qos(1000)

    assert qos.depth == 1000
    assert qos.reliability == ReliabilityPolicy.RELIABLE


def test_legacy_imu_qos_default_stays_best_effort_depth_50():
    qos = _best_effort_qos(50)

    assert qos.depth == 50
    assert qos.reliability == ReliabilityPolicy.BEST_EFFORT


def test_safe_shutdown_is_idempotent():
    if not rclpy.ok():
        rclpy.init(args=None)

    _safe_rclpy_shutdown()
    _safe_rclpy_shutdown()

    assert not rclpy.ok()
