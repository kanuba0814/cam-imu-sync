#!/usr/bin/env python3
"""Analyze cam_imu_sync events.csv — steady-clock-only metrics (v2).

Skips SYNC_OUT rows with imu_last_steady_ns == 0 (no valid IMU pairing).
Produces per-run + cross-run reports in the format requested.
"""

import csv
import math
import sys
import os
import glob


def analyze_run(csv_path: str, run_label: str) -> dict:
    """Parse one events.csv file and return summary dict."""
    print(f"\n{'='*72}")
    print(f"  {run_label}: {csv_path}")
    print(f"{'='*72}")

    first_cam_ns = None
    first_imu_ns = None
    deltas_ms = []
    total_sync_out = 0
    skipped_no_imu = 0

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
                if first_imu_ns is not None:
                    gap_ms = (first_cam_ns - first_imu_ns) / 1e6
                    print(f"  → cam_minus_imu_startup = {gap_ms:.1f} ms")

            elif evt == 'SYNC_OUT':
                total_sync_out += 1
                cam_steady   = int(row['cam_steady_ns']) if row['cam_steady_ns'] else 0
                target_align = int(row['target_align_ns']) if row['target_align_ns'] else 0
                imu_last     = int(row['imu_last_steady_ns']) if row['imu_last_steady_ns'] else 0
                cam_minus    = int(row['cam_minus_imu_last_ns']) if row['cam_minus_imu_last_ns'] else 0
                sync_id      = row.get('sync_frame_id', '?')

                if imu_last == 0:
                    skipped_no_imu += 1
                    continue

                delta_ms = cam_minus / 1e6
                deltas_ms.append(delta_ms)

                print(
                    f"  SYNC_OUT #{sync_id:>4s}  "
                    f"cam_host_steady_ns={cam_steady}  "
                    f"target_align_steady_ns={target_align}  "
                    f"imu_last_steady_ns={imu_last}  "
                    f"cam_minus_imu_last_steady_ns={cam_minus} "
                    f"({delta_ms:+.3f} ms)"
                )

    # ── summary ──────────────────────────────────────────────
    n = len(deltas_ms)
    print(f"\n  [info] total SYNC_OUT = {total_sync_out}, "
          f"skipped (imu_last=0) = {skipped_no_imu}, "
          f"valid = {n}")

    if n == 0:
        print("  ⚠  No valid SYNC_OUT events found!")
        return {}

    mean_ms = sum(deltas_ms) / n
    std_ms  = math.sqrt(sum((x - mean_ms)**2 for x in deltas_ms) / (n - 1)) if n > 1 else 0.0
    min_ms  = min(deltas_ms)
    max_ms  = max(deltas_ms)

    summary = {
        'n': n,
        'skipped': skipped_no_imu,
        'steady_cam_minus_imu_last_mean_ms': mean_ms,
        'steady_cam_minus_imu_last_std_ms':  std_ms,
        'steady_cam_minus_imu_last_min_ms':  min_ms,
        'steady_cam_minus_imu_last_max_ms':  max_ms,
    }

    print(f"\n  ── SUMMARY ({n} valid SYNC_OUT events) ──")
    print(f"  steady_cam_minus_imu_last_mean_ms = {mean_ms:.3f}")
    print(f"  steady_cam_minus_imu_last_std_ms  = {std_ms:.3f}")
    print(f"  steady_cam_minus_imu_last_min_ms  = {min_ms:.3f}")
    print(f"  steady_cam_minus_imu_last_max_ms  = {max_ms:.3f}")

    return summary


def main():
    log_base = "/home/gxxl/slam_ws_v2/extra_ws/logs/cam_imu_sync"

    if len(sys.argv) > 1:
        run_ids = sys.argv[1:]
    else:
        run_ids = sorted([
            os.path.basename(d) for d in glob.glob(os.path.join(log_base, 'steady_exp_*'))
            if os.path.isdir(d)
        ])

    if not run_ids:
        print("No runs found!")
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

    # ── cross-run table ──────────────────────────────────────
    if len(all_summaries) > 1:
        print(f"\n{'='*72}")
        print(f"  CROSS-RUN COMPARISON ({len(all_summaries)} runs)")
        print(f"{'='*72}")
        print(f"  {'run_id':<18s} {'mean_ms':>10s} {'std_ms':>10s} "
              f"{'min_ms':>10s} {'max_ms':>10s} {'valid':>6s} {'skip':>5s}")
        print(f"  {'-'*18} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*6} {'-'*5}")
        for rid, s in all_summaries:
            print(
                f"  {rid:<18s} "
                f"{s['steady_cam_minus_imu_last_mean_ms']:>10.3f} "
                f"{s['steady_cam_minus_imu_last_std_ms']:>10.3f} "
                f"{s['steady_cam_minus_imu_last_min_ms']:>10.3f} "
                f"{s['steady_cam_minus_imu_last_max_ms']:>10.3f} "
                f"{s['n']:>6d} "
                f"{s['skipped']:>5d}"
            )


if __name__ == '__main__':
    main()
