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
    _qos_reliability_name,
    _safe_rclpy_shutdown,
    _sensor_qos,
)


def test_sensor_qos_supports_best_effort_depth_1000():
    qos = _sensor_qos(1000, 'best_effort')

    assert qos.depth == 1000
    assert qos.reliability == ReliabilityPolicy.BEST_EFFORT


def test_sensor_qos_still_supports_reliable_depth_1000():
    qos = _sensor_qos(1000, 'reliable')

    assert qos.depth == 1000
    assert qos.reliability == ReliabilityPolicy.RELIABLE


def test_legacy_imu_qos_default_stays_best_effort_depth_50():
    qos = _best_effort_qos(50)

    assert qos.depth == 50
    assert qos.reliability == ReliabilityPolicy.BEST_EFFORT


def test_invalid_qos_reliability_falls_back_to_best_effort():
    assert _qos_reliability_name('invalid') == 'best_effort'


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
