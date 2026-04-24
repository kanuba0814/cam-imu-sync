#!/usr/bin/env python3
"""Analyze cam_imu_sync events.csv — steady-clock-only metrics.

Outputs:
  - FIRST_CAM_RX, FIRST_IMU_RX  (steady_ns)
  - Per SYNC_OUT:
      cam_host_steady_ns
      target_align_steady_ns        (target_align_ns : ROS aligned timestamp)
      imu_last_steady_ns
      cam_minus_imu_last_steady_ns  (纳秒 → 显示为 ms)
  - Summary:
      steady_cam_minus_imu_last_mean_ms
      steady_cam_minus_imu_last_std_ms
      steady_cam_minus_imu_last_min_ms
      steady_cam_minus_imu_last_max_ms
"""

import csv
import math
import sys
import os
import glob


def analyze_run(csv_path: str, run_label: str) -> dict:
    """Parse one events.csv file and return summary dict."""
    print(f"\n{'='*70}")
    print(f"  {run_label}: {csv_path}")
    print(f"{'='*70}")

    first_cam_ns = None
    first_imu_ns = None
    deltas_ms = []

    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            evt = row['event'].strip()

            if evt == 'FIRST_IMU_RX':
                first_imu_ns = int(row['steady_ns'])
                print(f"  FIRST_IMU_RX   steady_ns = {first_imu_ns}")

            elif evt == 'FIRST_CAM_RX':
                first_cam_ns = int(row['steady_ns'])
                print(f"  FIRST_CAM_RX   steady_ns = {first_cam_ns}")

            elif evt == 'SYNC_OUT':
                cam_steady     = int(row['cam_steady_ns']) if row['cam_steady_ns'] else 0
                target_align   = int(row['target_align_ns']) if row['target_align_ns'] else 0
                imu_last       = int(row['imu_last_steady_ns']) if row['imu_last_steady_ns'] else 0
                cam_minus_last = int(row['cam_minus_imu_last_ns']) if row['cam_minus_imu_last_ns'] else 0
                sync_id        = row.get('sync_frame_id', '?')

                delta_ms = cam_minus_last / 1e6
                deltas_ms.append(delta_ms)

                print(
                    f"  SYNC_OUT #{sync_id:>4s}  "
                    f"cam_host_steady_ns={cam_steady}  "
                    f"target_align_steady_ns={target_align}  "
                    f"imu_last_steady_ns={imu_last}  "
                    f"cam_minus_imu_last_steady_ns={cam_minus_last} "
                    f"({delta_ms:+.3f} ms)"
                )

    # ── summary ──────────────────────────────────────────────
    n = len(deltas_ms)
    if n == 0:
        print("\n  ⚠  No SYNC_OUT events found!")
        return {}

    mean_ms = sum(deltas_ms) / n
    std_ms  = math.sqrt(sum((x - mean_ms)**2 for x in deltas_ms) / (n - 1)) if n > 1 else 0.0
    min_ms  = min(deltas_ms)
    max_ms  = max(deltas_ms)

    summary = {
        'n': n,
        'steady_cam_minus_imu_last_mean_ms': mean_ms,
        'steady_cam_minus_imu_last_std_ms':  std_ms,
        'steady_cam_minus_imu_last_min_ms':  min_ms,
        'steady_cam_minus_imu_last_max_ms':  max_ms,
    }

    print(f"\n  ── SUMMARY ({n} SYNC_OUT events) ──")
    print(f"  steady_cam_minus_imu_last_mean_ms = {mean_ms:.3f}")
    print(f"  steady_cam_minus_imu_last_std_ms  = {std_ms:.3f}")
    print(f"  steady_cam_minus_imu_last_min_ms  = {min_ms:.3f}")
    print(f"  steady_cam_minus_imu_last_max_ms  = {max_ms:.3f}")

    return summary


def main():
    log_base = "/home/gxxl/slam_ws_v2/extra_ws/logs/cam_imu_sync"

    if len(sys.argv) > 1:
        # Explicit run IDs
        run_ids = sys.argv[1:]
    else:
        # Auto-detect steady_exp_* runs
        run_ids = sorted([
            os.path.basename(d) for d in glob.glob(os.path.join(log_base, 'steady_exp_*'))
            if os.path.isdir(d)
        ])

    if not run_ids:
        print("No runs found! Run the experiment first.")
        sys.exit(1)

    all_summaries = []
    for rid in run_ids:
        csv_path = os.path.join(log_base, rid, 'events.csv')
        if not os.path.exists(csv_path):
            print(f"⚠ {csv_path} not found, skipping")
            continue
        s = analyze_run(csv_path, rid)
        if s:
            all_summaries.append((rid, s))

    # ── cross-run comparison ─────────────────────────────────
    if len(all_summaries) > 1:
        print(f"\n{'='*70}")
        print(f"  CROSS-RUN COMPARISON ({len(all_summaries)} runs)")
        print(f"{'='*70}")
        print(f"  {'run_id':<20s} {'mean_ms':>10s} {'std_ms':>10s} {'min_ms':>10s} {'max_ms':>10s} {'N':>5s}")
        print(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*5}")
        for rid, s in all_summaries:
            print(
                f"  {rid:<20s} "
                f"{s['steady_cam_minus_imu_last_mean_ms']:>10.3f} "
                f"{s['steady_cam_minus_imu_last_std_ms']:>10.3f} "
                f"{s['steady_cam_minus_imu_last_min_ms']:>10.3f} "
                f"{s['steady_cam_minus_imu_last_max_ms']:>10.3f} "
                f"{s['n']:>5d}"
            )


if __name__ == '__main__':
    main()
