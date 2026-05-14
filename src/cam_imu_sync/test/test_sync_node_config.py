#!/usr/bin/env python3
# Copyright 2026 gxxl. MIT License.
"""Configuration helper tests for the ROS sync node wrapper."""

from __future__ import annotations

import rclpy
from rclpy.qos import ReliabilityPolicy

from cam_imu_sync.diagnostics import SUMMARY_COLUMNS
from cam_imu_sync.sync_node import (
    _best_effort_qos,
    _input_imu_rate_hz,
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


def test_summary_keeps_input_imu_rate_and_compat_alias():
    assert 'input_imu_rate_hz' in SUMMARY_COLUMNS
    assert 'observed_sync_imu_rate_hz' in SUMMARY_COLUMNS
    assert SUMMARY_COLUMNS.index('input_imu_rate_hz') < SUMMARY_COLUMNS.index(
        'observed_sync_imu_rate_hz')


def test_input_imu_rate_prefers_counted_window_rate():
    assert _input_imu_rate_hz(199.5, 5.2) == 199.5


def test_input_imu_rate_falls_back_to_period_mean():
    assert _input_imu_rate_hz(0.0, 5.0) == 200.0
    assert _input_imu_rate_hz(0.0, 0.0) == 0.0


def test_safe_shutdown_is_idempotent():
    if not rclpy.ok():
        rclpy.init(args=None)

    _safe_rclpy_shutdown()
    _safe_rclpy_shutdown()

    assert not rclpy.ok()
