#!/usr/bin/env python3
# Copyright 2026 gxxl. MIT License.
"""Structured terminal diagnostics for cam_imu_sync.

All records go through the ROS 2 logger.  ROS 2 launch captures the same output
in its normal log directory, so this module intentionally does not create
per-run directories, CSV files, or metadata files.
"""

from __future__ import annotations

import math
import threading
from typing import Optional


# ── CSV column schema ────────────────────────────────────────────────
# Wide format — unused fields across event types are left blank.

CSV_COLUMNS = [
    'event', 'steady_ns',
    # camera
    'cam_frame_id', 'cam_header_ns', 'cam_steady_ns',
    # imu
    'imu_id', 'imu_header_ns',
    # sync
    'sync_frame_id',
    'sync_decision_steady_ns', 'publish_steady_ns',
    'target_align_ns', 'applied_offset_ns',
    'target_align_steady_ns', 'applied_steady_offset_ns',
    'imu_first_id', 'imu_last_id', 'imu_count',
    'imu_first_steady_ns', 'imu_last_steady_ns',
    'interp_used',
    'cam_minus_imu_last_ns',
    # state machine
    'new_state',
    # shared
    'queue_depth',
    # imu data
    'ax', 'ay', 'az', 'gx', 'gy', 'gz',
    # Phase 1A
    'imu_tid',
    'unified_stamp_ns',
    'ros_minus_steady_offset_ns',
    'extra',
]

SYNC_FRAME_COLUMNS = [
    'steady_ns', 'sync_frame_id', 'cam_frame_id',
    'cam_header_ns', 'cam_steady_ns', 'target_align_ns',
    'target_align_steady_ns', 'applied_offset_ns',
    'applied_steady_offset_ns', 'imu_first_id', 'imu_last_id',
    'imu_count', 'imu_first_steady_ns', 'imu_last_steady_ns',
    'interp_used', 'cam_minus_imu_last_ns',
]

RESAMPLED_IMU_COLUMNS = [
    'steady_ns', 'target_steady_ns', 'header_stamp_ns',
    'source_kind', 'before_steady_ns', 'after_steady_ns', 'alpha',
    'gap_ns', 'ax', 'ay', 'az', 'gx', 'gy', 'gz',
]

SUMMARY_COLUMNS = [
    'steady_ns', 'state', 'synced_frames', 'dropped_frames',
    'interp_count', 'sync_batch_imu', 'batch_imu_pub',
    'resampled_imu_pub', 'resample_gap_skip', 'observed_sync_imu_rate_hz',
    'imu_mean_period_ms', 'imu_period_std_ms', 'cam_mean_period_ms',
    'sync_fails', 'resets',
]


# ── running statistics (Welford) ─────────────────────────────────────

class OnlineStats:
    """Single-pass running mean and standard deviation (Welford)."""

    __slots__ = ('n', '_mean', '_m2')

    def __init__(self) -> None:
        self.n = 0
        self._mean = 0.0
        self._m2 = 0.0

    def update(self, x: float) -> None:
        self.n += 1
        d1 = x - self._mean
        self._mean += d1 / self.n
        d2 = x - self._mean
        self._m2 += d1 * d2

    @property
    def mean(self) -> float:
        return self._mean if self.n > 0 else 0.0

    @property
    def std(self) -> float:
        return math.sqrt(self._m2 / (self.n - 1)) if self.n >= 2 else 0.0


# ── ROS logger event writer ───────────────────────────────────────────

class DiagnosticsWriter:
    """Thread-safe structured ROS logger for debug events."""

    def __init__(
        self,
        logger,
        run_meta: Optional[dict] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._logger = logger
        self._closed = False
        if run_meta:
            self._emit('sync_meta', run_meta)

    # ── low-level writer ─────────────────────────────────────────────

    def _emit(self, prefix: str, row: dict) -> None:
        msg = ' '.join(f'{k}={v}' for k, v in row.items() if v != '')
        with self._lock:
            if not self._closed:
                self._logger.info(f'[{prefix}] {msg}')

    def _row(self, event: str, **kw) -> None:
        row = {c: '' for c in CSV_COLUMNS}
        row['event'] = event
        row.update(kw)
        self._emit(f'sync_{event.lower()}', row)

    def _structured_row(
        self, prefix: str, columns: list[str], **kw,
    ) -> None:
        row = {c: '' for c in columns}
        row.update(kw)
        self._emit(prefix, row)

    # ── public event helpers ─────────────────────────────────────────

    def run_start(self, steady_ns: int, **extra) -> None:
        """Record RUN_START event with optional extra key=value pairs."""
        self._row('RUN_START', steady_ns=steady_ns,
                  extra=';'.join(f'{k}={v}' for k, v in extra.items())
                  if extra else '')

    def first_event(self, event: str, steady_ns: int) -> None:
        """Record a milestone event (FIRST_CAM_RX / FIRST_IMU_RX)."""
        self._row(event, steady_ns=steady_ns)

    def cam_rx(
        self, cam_frame_id: int, cam_header_ns: int,
        steady_ns: int, queue_depth: int,
    ) -> None:
        """Record a camera frame reception event."""
        self._row('CAM_RX', steady_ns=steady_ns,
                  cam_frame_id=cam_frame_id,
                  cam_header_ns=cam_header_ns,
                  queue_depth=queue_depth)

    def imu_rx(
        self, imu_id: int, imu_header_ns: int,
        steady_ns: int, queue_depth: int,
        ax: float, ay: float, az: float,
        gx: float, gy: float, gz: float,
        extra: str = '',
    ) -> None:
        """Record an IMU sample reception event."""
        self._row('IMU_RX', steady_ns=steady_ns,
                  imu_id=imu_id,
                  imu_header_ns=imu_header_ns,
                  queue_depth=queue_depth,
                  ax=f'{ax:.6f}', ay=f'{ay:.6f}', az=f'{az:.6f}',
                  gx=f'{gx:.6f}', gy=f'{gy:.6f}', gz=f'{gz:.6f}',
                  extra=extra)

    def sync_out(
        self, *,
        sync_frame_id: int,
        cam_frame_id: int,
        cam_header_ns: int,
        cam_steady_ns: int,
        sync_decision_steady_ns: int,
        publish_steady_ns: int,
        imu_first_id: int,
        imu_last_id: int,
        imu_count: int,
        imu_first_steady_ns: int,
        imu_last_steady_ns: int,
        interp_used: bool,
        target_align_ns: int,
        applied_offset_ns: int,
        cam_minus_imu_last_ns: int,
        target_align_steady_ns: int = 0,
        applied_steady_offset_ns: int = 0,
    ) -> None:
        """Record a synchronisation output event."""
        self._row(
            'SYNC_OUT',
            steady_ns=publish_steady_ns,
            sync_frame_id=sync_frame_id,
            cam_frame_id=cam_frame_id,
            cam_header_ns=cam_header_ns,
            cam_steady_ns=cam_steady_ns,
            sync_decision_steady_ns=sync_decision_steady_ns,
            publish_steady_ns=publish_steady_ns,
            target_align_ns=target_align_ns,
            applied_offset_ns=applied_offset_ns,
            target_align_steady_ns=target_align_steady_ns,
            applied_steady_offset_ns=applied_steady_offset_ns,
            imu_first_id=imu_first_id,
            imu_last_id=imu_last_id,
            imu_count=imu_count,
            imu_first_steady_ns=imu_first_steady_ns,
            imu_last_steady_ns=imu_last_steady_ns,
            interp_used=1 if interp_used else 0,
            cam_minus_imu_last_ns=cam_minus_imu_last_ns,
        )
        self._structured_row(
            'sync_frame',
            SYNC_FRAME_COLUMNS,
            steady_ns=publish_steady_ns,
            sync_frame_id=sync_frame_id,
            cam_frame_id=cam_frame_id,
            cam_header_ns=cam_header_ns,
            cam_steady_ns=cam_steady_ns,
            target_align_ns=target_align_ns,
            target_align_steady_ns=target_align_steady_ns,
            applied_offset_ns=applied_offset_ns,
            applied_steady_offset_ns=applied_steady_offset_ns,
            imu_first_id=imu_first_id,
            imu_last_id=imu_last_id,
            imu_count=imu_count,
            imu_first_steady_ns=imu_first_steady_ns,
            imu_last_steady_ns=imu_last_steady_ns,
            interp_used=1 if interp_used else 0,
            cam_minus_imu_last_ns=cam_minus_imu_last_ns,
        )

    def resampled_imu(
        self, *,
        steady_ns: int,
        target_steady_ns: int,
        header_stamp_ns: int,
        source_kind: str,
        before_steady_ns: int,
        after_steady_ns: int,
        alpha: float,
        gap_ns: int,
        ax: float, ay: float, az: float,
        gx: float, gy: float, gz: float,
    ) -> None:
        """Record one fixed-rate /sync/imu output point."""
        self._structured_row(
            'sync_resampled_imu',
            RESAMPLED_IMU_COLUMNS,
            steady_ns=steady_ns,
            target_steady_ns=target_steady_ns,
            header_stamp_ns=header_stamp_ns,
            source_kind=source_kind,
            before_steady_ns=before_steady_ns,
            after_steady_ns=after_steady_ns,
            alpha=f'{alpha:.9f}',
            gap_ns=gap_ns,
            ax=f'{ax:.6f}', ay=f'{ay:.6f}', az=f'{az:.6f}',
            gx=f'{gx:.6f}', gy=f'{gy:.6f}', gz=f'{gz:.6f}',
        )

    # ── NEW: state machine events ────────────────────────────────────

    def state_change(
        self, new_state: str, steady_ns: int, extra: str = '',
    ) -> None:
        """Record a state machine transition event."""
        self._row('STATE_CHANGE', steady_ns=steady_ns,
                  new_state=new_state, extra=extra)

    def sync_fail(
        self, steady_ns: int, reason: str = '',
    ) -> None:
        """Record a sync failure event."""
        self._row('SYNC_FAIL', steady_ns=steady_ns, extra=reason)

    def rearm_event(
        self, steady_ns: int, reason: str = '',
    ) -> None:
        """Record a re-arm event."""
        self._row('REARM', steady_ns=steady_ns, extra=reason)

    # ── summary ──────────────────────────────────────────────────────

    def write_summary(self, summary: dict) -> None:
        """Record final summary at end of run."""
        self._emit('sync_run_summary', summary)

    def summary_1hz(self, **kw) -> None:
        """Record one periodic debug summary row."""
        self._structured_row('sync_summary', SUMMARY_COLUMNS, **kw)

    # ── lifecycle ────────────────────────────────────────────────────

    def close(self) -> None:
        with self._lock:
            self._closed = True


class NullDiagnosticsWriter:
    """No-op diagnostics writer for debug_enable=false."""

    def run_start(self, *args, **kwargs) -> None:
        pass

    def first_event(self, *args, **kwargs) -> None:
        pass

    def cam_rx(self, *args, **kwargs) -> None:
        pass

    def imu_rx(self, *args, **kwargs) -> None:
        pass

    def sync_out(self, *args, **kwargs) -> None:
        pass

    def resampled_imu(self, *args, **kwargs) -> None:
        pass

    def state_change(self, *args, **kwargs) -> None:
        pass

    def sync_fail(self, *args, **kwargs) -> None:
        pass

    def rearm_event(self, *args, **kwargs) -> None:
        pass

    def write_summary(self, *args, **kwargs) -> None:
        pass

    def summary_1hz(self, *args, **kwargs) -> None:
        pass

    def close(self) -> None:
        pass


# ── utility: build run metadata dict ─────────────────────────────────

def build_run_meta(
    cfg,
    *,
    camera_fps: int = 30,
    imu_rate_cfg: int = 200,
    imu_baudrate: int = 460800,
) -> dict:
    """Assemble the meta.txt content from config and system info."""
    return {
        'camera_driver': 'usb_cam',
        'imu_driver': 'yesense_std_ros2',
        'camera_fps': str(camera_fps),
        'imu_rate_cfg': str(imu_rate_cfg),
        'imu_baudrate': str(imu_baudrate),
        'sync_offset_param': f'{cfg.cam_imu_time_offset:.6f}',
        'steady_cam_to_imu_offset_sec':
            f'{cfg.steady_cam_to_imu_offset_sec:.6f}',
        'enable_interpolation': str(cfg.enable_interpolation),
        'max_sync_wait_ms': f'{cfg.max_sync_wait_sec * 1000:.1f}',
        'max_interp_gap_ms': f'{cfg.max_interp_gap_sec * 1000:.1f}',
        'drop_frame_on_missing_imu': str(cfg.drop_frame_on_missing_imu),
        'max_image_queue_size': str(cfg.max_image_queue_size),
        'exposure': 'auto',
        'camera_format': 'yuyv',
        # state-machine params
        'camera_startup_drop_sec': f'{cfg.camera_startup_drop_sec:.1f}',
        'sync_wait_imu_ready_min_samples':
            str(cfg.sync_wait_imu_ready_min_samples),
        'sync_wait_imu_ready_max_std_ms':
            f'{cfg.sync_wait_imu_ready_max_std_ms:.1f}',
        'sync_fail_consecutive_limit':
            str(cfg.sync_fail_consecutive_limit),
        'first_sync_timeout_sec': f'{cfg.first_sync_timeout_sec:.1f}',
        'first_sync_drop_limit': str(cfg.first_sync_drop_limit),
    }
