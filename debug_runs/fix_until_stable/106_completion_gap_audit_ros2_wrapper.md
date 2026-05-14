# Completion Gap Audit: ROS2 wrapper validation still required

Superseded in part: this audit predates experiments 20-25 and still names the
older experiment 20 branch as the next action. The current execution path is
experiment 25 in `141_resume_manifest_after_docker_approval.md`.

## Objective Restatement
The H30 sync-only fixed bag must be stable through the ROS2 wrapper path, not an
ORB-SLAM3 standalone executable and not an explanation-only report. Completion
requires at least three consecutive full-bag replays through
`orb_slam3_ros2 h30_bag_replay.launch.py` that pass every stability gate, followed
by final artifacts.

## Prompt-to-Artifact Checklist

| Requirement | Current Evidence | Status |
| --- | --- | --- |
| Use fixed bag from `bags/LATEST_BAG.txt` | `run_stability_replay.py --preflight-only --timeout-sec 210` resolved `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136` | Covered for preflight |
| Use only sync replay topics and do not depend on `/image_raw` | Preflight selected replay topics `/sync/image_raw,/sync/imu` and ignored `/image_raw, /imu/data_raw, /imu/raw_hw` | Covered for current harness |
| Validate through ROS2 wrapper | Final gate requires command parts `ros2 launch orb_slam3_ros2 h30_bag_replay.launch.py` | Covered by gate, not yet passing in real replay |
| Three consecutive full replays | Latest real aggregate `19_frames_to_reset_90` has `run_count=3` | Present but failing |
| IMU initializes | `19_frames_to_reset_90.md` shows all three runs `IMU Init=True` | Passing only this item |
| No reset increase after init | `19_frames_to_reset_90.md` shows reset-after-init values `3, 3, 7` | Failing |
| OK ratio after init >= 0.90 | `19_frames_to_reset_90.md` shows `0.6890, 0.6890, 0.7712` | Failing |
| No long LOST/RECENTLY_LOST | Not accepted because aggregate fails final gates | Unverified/presumed failing path |
| No reset in last 60 seconds | Not accepted because aggregate fails final gates | Unverified in final format |
| Final keyframes >= 20 | `19_frames_to_reset_90.md` shows `33, 33, 21` | Passing this item |
| Median map points >= 80 | `19_frames_to_reset_90.md` shows `166, 169, 117` | Passing this item |
| Median inliers >= 50 | `19_frames_to_reset_90.md` shows `166, 169, 116` | Passing this item |
| Processed image age p95 < 150 ms | `19_frames_to_reset_90.md` shows `18.63, 16.21, 15.77` ms | Passing this item |
| Controlled backlog | `19_frames_to_reset_90.md` shows `Backlog OK=True`, `Img Buf Max=1` | Passing this item |
| No invalid pose publishes | `19_frames_to_reset_90.md` shows `0` invalid pose publishes | Passing this item |
| Final artifacts | No `final_stability_report.md`, `best_config.yaml`, `final_patch_summary.md`, or `final_commands.md` from a passing aggregate | Missing |

## Current Blocker
At `2026-05-15 02:33 JST`, git staging in the nested wrapper repo still requires
escalated permission because `.git/index.lock` cannot be created from the
sandbox. The automatic escalation review is unavailable until the previously
reported `05:26 AM` window, so source commits and Docker/container replay should
not be retried yet.

## Next Minimal Action When Permission Returns
1. Commit the already-validated final-gate hardening in:
   - `tools/generate_final_stability_artifacts.py`
   - `tools/selftest_final_stability_gates.py`
2. Apply one behavior change only: set
   `Tracking.ResetActiveMapBeforeInertialBA2: 0` on top of the current
   `Tracking.FramesToResetIMU: 90` baseline.
3. Build `orb_slam3_ros2` inside `autoware_env_v2_host`.
4. Run three full ROS2 wrapper replays with label
   `20_frames90_no_pre_ba2_reset`.
5. Keep the change only if the aggregate passes or provides evidence that the
   behavior should be retained; otherwise revert the behavior commit before the
   next experiment.
