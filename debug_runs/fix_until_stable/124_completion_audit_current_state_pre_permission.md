# Completion Audit: current state before permission restores

Superseded: this audit records the pre-experiment-20 permission-blocked state.
The current readiness audit is
`140_pre_replay_readiness_audit_experiment25.md`, and the current resume
manifest is `141_resume_manifest_after_docker_approval.md`.

## Objective
Fix the H30 sync-only fixed bag through the ROS2 wrapper path. Completion is not
an explanation: it requires committed code/config changes, containerized build,
three consecutive full-bag `orb_slam3_ros2` wrapper replays, all stability gates
passing, and final artifacts.

## Current Evidence Snapshot
- Current time checked: `2026-05-15 02:54 JST`
- Latest real replay aggregate: `19_frames_to_reset_90`
- Bag: `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136`
- Aggregate result: `run_count=3`, `pass_count=0`, `all_passed=false`
- Current parser recheck: all three runs have `stability_pass=false`
- Runtime errors: run 1 and run 2 each have `runtime_error_count=1`

## Prompt-to-Artifact Checklist

| Requirement | Evidence | Status |
| --- | --- | --- |
| Use ROS2 wrapper, not standalone ORB examples | Final gate requires `ros2 launch orb_slam3_ros2 h30_bag_replay.launch.py`; launch is wrapper-only per evidence `109` | Covered by gate |
| Use fixed latest bag | Both latest-bag files resolve to `h30_sync_raw_20260512_172136`; evidence `120` | Covered |
| Do not start real camera/IMU/sync nodes | `h30_bag_replay.launch.py` starts wrapper and optional bag play only; evidence `109` | Covered |
| Do not depend on `/image_raw` | Preflight selects `/sync/image_raw,/sync/imu` and ignores raw topics; evidence `111` | Covered |
| Full-bag replay, no skipped prefix | Final gate requires `duration:=0.0`, `start_offset:=0.0`, full bag duration, adequate timeout; evidence `112` | Covered by gate |
| Three consecutive replay runs | Latest aggregate has three runs, but `pass_count=0` | Failing |
| IMU initialized in every run | Run 19 parser shows IMU initialized, but this alone is not success | Insufficient |
| No reset growth after init | Run 19 reset after init is `3, 3, 7` | Failing |
| OK ratio after init >= 0.90 | Run 19 OK ratio is `0.6890, 0.6890, 0.7712` | Failing |
| No reset in final 60 seconds | Current parser reports `reset_delta_last_60_sec=4` in all runs | Failing |
| No long LOST/RECENTLY_LOST | Current run 19 does not pass aggregate gates; old no-reset run had ~5s streaks per evidence `122` | Not passing |
| Final KFs >= 20 | Run 19 has `33, 33, 21` | Passing this item only |
| Median MPs >= 80 | Run 19 has `166, 169, 117` | Passing this item only |
| Median inliers >= 50 | Run 19 has `166, 169, 116` | Passing this item only |
| IMU lag sane | Run 19 image-to-last-IMU p95 below `10ms` | Passing this item only |
| Processed image age p95 < 150ms | Run 19 p95 below `20ms` | Passing this item only |
| Controlled backlog | Run 19 max image buffer `1`, controlled backlog true | Passing this item only |
| No invalid pose publishes | Run 19 invalid pose publishes `0` | Passing this item only |
| Runtime errors rejected | Current parser catches `exit code -11` in run 1 and run 2; evidence `116`, `118`, `119` | Failing |
| Final artifact names available | Generator writes all required final files; evidence `108` | Covered by gate |
| Final artifacts generated from passing aggregate | No passing aggregate exists | Missing |
| Every source change committed | Current final-gate source changes are still uncommitted due permission block | Blocked |
| Next change is one minimal behavior experiment | Manifest `121` defines the separate no-reset config experiment | Pending |

## Current Blocker
The system is still before the previously reported `05:26 AM` permission window.
Nested git staging and Docker/container replay should not be retried before that
window. Current wrapper repo source diff is limited to:

```text
tools/generate_final_stability_artifacts.py
tools/selftest_final_stability_gates.py
```

## Decision
The goal is not achieved. The next concrete execution step after permissions
return is still:

1. Commit the final-gate hardening.
2. Apply and commit `Tracking.ResetActiveMapBeforeInertialBA2: 0`.
3. Build in `autoware_env_v2_host`.
4. Run `20_frames90_no_pre_ba2_reset` as three full ROS2 wrapper replays.
5. Keep or revert based on the aggregate gates, including `runtime_error_count=0`.
