#!/usr/bin/env python3
# Copyright 2026 gxxl. MIT License.
"""Unit tests for the fixed-rate IMU resampler."""

from __future__ import annotations

import pytest

from cam_imu_sync.fixed_rate_resampler import FixedRateImuResampler


def _push_200hz_samples(
    resampler: FixedRateImuResampler,
    *,
    start_ns: int,
    count: int,
    frame_id: str = 'imu_link',
) -> None:
    for i in range(count):
        steady_ns = start_ns + i * 5_000_000
        value = steady_ns / 1e6
        resampler.push_sample(
            steady_ns=steady_ns,
            frame_id=frame_id,
            lin_acc=(value, 0.0, 9.81),
            ang_vel=(value, 0.0, 0.0),
        )


class TestFixedRateImuResampler:
    def test_100hz_outputs_one_point_per_poll(self):
        resampler = FixedRateImuResampler(
            rate_hz=100.0,
            latency_ms=20.0,
            max_gap_ms=15.0,
        )

        _push_200hz_samples(resampler, start_ns=0, count=16)  # latest=75 ms

        out1 = resampler.poll()
        assert out1.kind == 'publish'
        assert out1.point is not None
        assert out1.point.target_steady_ns % 10_000_000 == 0
        assert out1.point.target_steady_ns == 50_000_000

        out2 = resampler.poll()
        assert out2.kind == 'wait'

        _push_200hz_samples(resampler, start_ns=80_000_000, count=2)
        out3 = resampler.poll()
        assert out3.kind == 'publish'
        assert out3.point is not None
        assert out3.point.target_steady_ns == 60_000_000

    def test_150hz_interpolates_on_fractional_grid(self):
        resampler = FixedRateImuResampler(
            rate_hz=150.0,
            latency_ms=20.0,
            max_gap_ms=15.0,
        )

        _push_200hz_samples(resampler, start_ns=0, count=15)  # latest=70 ms

        out = resampler.poll()
        assert out.kind == 'publish'
        assert out.point is not None
        assert out.point.target_steady_ns == 46_666_666
        assert out.point.lin_acc[0] == pytest.approx(46.666666, abs=1e-3)
        assert out.point.ang_vel[0] == pytest.approx(46.666666, abs=1e-3)

    def test_large_timer_delay_fast_forwards_without_burst(self):
        resampler = FixedRateImuResampler(
            rate_hz=100.0,
            latency_ms=20.0,
            max_gap_ms=15.0,
        )

        _push_200hz_samples(resampler, start_ns=0, count=41)  # latest=200 ms

        out = resampler.poll()
        assert out.kind == 'publish'
        assert out.point is not None
        assert out.point.target_steady_ns == 180_000_000

        # A second poll without new source IMU must not replay backlog.
        out2 = resampler.poll()
        assert out2.kind == 'wait'

    def test_large_source_gap_is_skipped_and_next_grid_recovers(self):
        resampler = FixedRateImuResampler(
            rate_hz=100.0,
            latency_ms=5.0,
            max_gap_ms=10.0,
        )

        resampler.push_sample(
            steady_ns=0,
            frame_id='imu_link',
            lin_acc=(0.0, 0.0, 9.81),
            ang_vel=(0.0, 0.0, 0.0),
        )
        resampler.push_sample(
            steady_ns=5_000_000,
            frame_id='imu_link',
            lin_acc=(5.0, 0.0, 9.81),
            ang_vel=(5.0, 0.0, 0.0),
        )
        resampler.push_sample(
            steady_ns=30_000_000,
            frame_id='imu_link',
            lin_acc=(30.0, 0.0, 9.81),
            ang_vel=(30.0, 0.0, 0.0),
        )

        skipped = resampler.poll()
        assert skipped.kind == 'skip'
        assert skipped.target_steady_ns == 20_000_000
        assert skipped.gap_ns == 25_000_000

        resampler.push_sample(
            steady_ns=35_000_000,
            frame_id='imu_link',
            lin_acc=(35.0, 0.0, 9.81),
            ang_vel=(35.0, 0.0, 0.0),
        )
        published = resampler.poll()
        assert published.kind == 'publish'
        assert published.point is not None
        assert published.point.target_steady_ns == 30_000_000
