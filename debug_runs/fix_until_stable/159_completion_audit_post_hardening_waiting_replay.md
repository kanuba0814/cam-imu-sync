# Completion Audit: Post-Hardening Waiting For Wrapper Replay

## Objective Restatement

The goal is not to stop at diagnosis. ORB_SLAM3_ROS2 plus ORB_SLAM3 must be
modified, built, and validated on the fixed H30 sync-only ROS2 bag until the
fixed bag reaches stable mapping/localization. Completion requires real
containerized ROS2 wrapper replay evidence, not standalone ORB evidence and not
explanation-only artifacts.

## Current Candidate Under Audit

- Wrapper repo HEAD: `067c63e test: reject timed-out H30 final replays`
- Current H30 behavior candidate:
  `f93a5c7 fix: allow H30 post-init visual dropout survival`
- ORB core HEAD: `a5ea5b1 fix: allow delaying monocular IMU initialization`
- Fixed bag:
  `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136`
- Expected aggregate:
  `extra_ws/debug_runs/fix_until_stable/30_postinit_inliers0_wrapper_pose_gate_full_window.json`

## Prompt-To-Artifact Checklist

| Requirement | Current Evidence | Status |
| --- | --- | --- |
| Use fixed latest H30 sync-only bag | `158_evidence_post_hardening_preflight_metadata.md` records the current bag path and preflight metadata. | Satisfied for preflight only |
| Do not depend on `/image_raw` or raw IMU topics | Preflight ignores `/image_raw`, `/imu/data_raw`, `/imu/raw_hw`; selected replay topics are `/sync/image_raw,/sync/imu`. | Satisfied for preflight only |
| Do not launch real camera, real IMU, or live cam_imu_sync | `h30_bag_replay.launch.py` plus `run_stability_replay.py` launch only `orb_slam3_ros2` wrapper and optional bag play. Final gate requires this command. | Satisfied by harness |
| ROS2 wrapper path, not standalone ORB | Final generator requires `ros2 launch orb_slam3_ros2 h30_bag_replay.launch.py`. | Satisfied by harness |
| Explicit wrapper pose protection | `run_stability_replay.py` now passes `min_pose_publish_inliers:=15` and `min_pose_publish_tracked_mappoints:=15`; final generator rejects missing or altered values. | Satisfied by harness |
| QoS override topic names match sync bag topics | `fd08b28` makes preflight parse `bag_qos_override.yaml` and require exactly `/sync/image_raw`, `/sync/imu`, `/sync/imu_batch`. | Satisfied by harness |
| Timeout cleanup cannot contaminate later runs | `342ae01` runs each ROS2 wrapper replay in a new process group and kills that group on timeout before parsing/writing run evidence. `067c63e` makes final artifacts reject missing or true `timed_out` evidence. | Satisfied by harness |
| Final gate rejects fake pose publishing | Parser counts `invalid_pose_publish_count`; final gate requires `0`. | Satisfied by harness |
| IMU initialized is not accepted alone | Final gate additionally requires reset, OK ratio, lost streak, keyframes, map points, inliers, IMU timing, image age, queue/backlog, and invalid pose gates. | Satisfied by harness |
| Consecutive 3 offline wrapper replays pass | `30_postinit_inliers0_wrapper_pose_gate_full_window.json` does not exist. | Missing |
| Containerized build before replay | Docker escalation is still blocked by the approval retry window; no post-hardening container build has run. | Missing |
| Per-run stable success metrics | No real post-hardening replay aggregate exists. | Missing |
| Final `best_config.yaml` | Not present in `fix_until_stable/`. | Missing |
| Final `decision.md` | Not present in `fix_until_stable/`. | Missing |
| Final `stability_report.md` | Not present in `fix_until_stable/`. | Missing |
| Final `final_stability_report.md` | Not present in `fix_until_stable/`. | Missing |
| Final default launch/config supported by evidence | Candidate config and launch are committed and preflighted, but not yet behavior-validated by 3 replay runs. | Incomplete |

## Verification Performed In This Audit

Commands run from `/home/gxxl/slam_ws_v2`:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py \
  --runs 1 \
  --label 30_postinit_inliers0_wrapper_pose_gate_full_window \
  --timeout-sec 210 \
  --min-pose-publish-inliers 15 \
  --min-pose-publish-tracked-mappoints 15 \
  --preflight-only
```

Result:

```text
preflight: ignoring non-replay bag topics: /image_raw, /imu/data_raw, /imu/raw_hw
preflight passed for /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
replay_topics: /sync/image_raw,/sync/imu
start_offset_sec: 0.0
```

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/selftest_final_stability_gates.py
```

Result:

```text
preflight: ignoring non-replay bag topics: /image_raw, /imu/data_raw, /imu/raw_hw
final stability gate selftest passed
```

Current file check:

```text
No 30_postinit_inliers0_wrapper_pose_gate_full_window* files are present.
No final_stability_report.md, best_config.yaml, decision.md, stability_report.md,
final_patch_summary.md, or final_commands.md are present.
```

## Completion Decision

The goal is not complete. The harness is ready and stricter than before, but
there is no real containerized 3-run ROS2 wrapper replay aggregate for the
current candidate. Do not call `update_goal complete`. The next required action
is the containerized build and 3-run replay recorded in
`157_next_container_replay_after_gate_hardening.md`.
