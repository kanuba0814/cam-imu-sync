# Completion gate coverage audit

## Objective restatement

Fix `ORB_SLAM3_ROS2` + `ORB_SLAM3` for the fixed H30 sync-only ROS 2 bag. Completion requires a closed loop of diagnosis, one minimal explainable change, commit, containerized build, fixed-bag ROS 2 wrapper replay, and evidence. The goal is complete only when the fixed bag passes the stability criteria for at least three consecutive offline replays and the final report artifacts are generated.

## Current state

- Current behavioral baseline: `14_revert_preinit_inliers_35`
- Result: `pass_count=0/3`
- Latest wrapper validation-tooling commit: `e9df367 test: recompute final stability gates`
- Latest evidence commit in `extra_ws`: `d620a23 debug: document final gate recomputation evidence`
- Next behavioral hypothesis already documented: set H30 `Camera.fps` to `9`
- Current blocker: `autoware_env_v2_host` Docker access is not available until the approval window reopens, so the next behavior change is not applied yet.
- Next real replay timeout: `--timeout-sec 210`; `180` seconds is rejected by preflight for the full fixed bag.

## Prompt-to-artifact checklist

| Requirement | Current artifact or evidence | Status |
| --- | --- | --- |
| Use fixed sync-only bag | `run_stability_replay.py` reads `bags/LATEST_BAG.txt` or explicit `--bag-path`; `30_evidence_camera_fps_bag_rate.md` identifies `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136`; aggregate preflight records bag path and bag topics | Covered |
| Do not require `/image_raw` | `h30_bag_replay.launch.py` defaults to `/sync/image_raw`; `run_stability_replay.py` rejects selected `/image_raw`; final artifact generator rejects forbidden selected topics | Covered |
| Do not start real camera driver | `h30_bag_replay.launch.py` starts ORB wrapper, optional `ros2 bag play`, optional RViz only | Covered |
| Do not start real IMU driver | `h30_bag_replay.launch.py` starts ORB wrapper, optional `ros2 bag play`, optional RViz only | Covered |
| Do not start live `cam_imu_sync` | `h30_bag_replay.launch.py` comment and actions exclude `cam_imu_sync` | Covered |
| Validate through ROS 2 wrapper | `run_stability_replay.py` launches `ros2 launch orb_slam3_ros2 h30_bag_replay.launch.py`; final artifact generator rejects run commands that are not the guarded wrapper launch path | Covered |
| Build/test/run inside `autoware_env_v2_host` | Workspace `AGENTS.md` and memory rule require containerized ROS validation | Covered but currently blocked |
| Do not treat `imu_initialized=true` alone as success | `parse_runtime_orb_log.py` requires all stability gates, not just IMU init | Covered |
| At least 3 offline replays pass | `run_stability_replay.py --runs 3`; aggregate requires all runs to pass and return code 0; final artifact generator requires at least three passing runs and recomputes each final stability gate from metrics | Covered, currently failing |
| IMU initialized each run | `imu_initialized` gate in parser | Covered |
| Reset count does not increase after init | `reset_count_after_init == 0` gate | Covered, currently failing |
| OK ratio after init >= 0.90 | `ok_ratio_after_init >= 0.90` gate | Covered, currently failing |
| No long RECENTLY_LOST or LOST after init | `max_lost_streak_sec_after_init < 5.0` gate | Covered |
| No active map reset in last 60 seconds | `reset_delta_last_60_sec == 0` gate | Covered, currently failing in some runs |
| Final keyframes >= 20 | `final_keyframes >= 20` gate | Covered |
| Median tracked map points >= 80 | `median_tracked_map_points_after_init >= 80` gate | Covered, currently failing in run 2 |
| Median inliers >= 50 | `median_inliers_after_init >= 50` gate | Covered, currently failing in run 2 |
| `image_to_last_imu_ms` p50/p95 has no abnormal jump | Parser emits p50/p95/max and gates p95 with `abs(p95) <= 20.0` | Covered with numeric threshold |
| `processed_image_age_ms` p95 < 150 ms | Parser gates `processed_image_age_ms.p95 < 150.0` | Covered |
| `img_buf_size` does not grow unbounded | Parser gates `img_buf_size_max <= 2` and now emits final/max queue values | Covered |
| ORB processed FPS or controlled drop is stable | Parser now emits `orb_processed_fps_est` and `controlled_backlog_pass` | Covered |
| Do not publish fake pose while invalid | Parser counts `invalid_pose_publish_count == 0` from `[orb_pose_gate]` | Covered |
| Replay settings provenance | Aggregate Markdown and final report include `settings_file`, `settings_camera_fps`, QoS override, image FPS, timeout, rate, and play delay | Covered |
| Full fixed-bag timeout | `run_stability_replay.py` computes `required_timeout_sec`; `45_evidence_timeout_guard_for_full_bag_replay.md` shows `--timeout-sec 180` rejected and `210` accepted | Covered |
| Final `best_config.yaml` | Not generated for a passing final state; generator refuses incomplete, non-wrapper, or gate-inconsistent evidence | Missing |
| Final `decision.md` | Not generated for a passing final state; generator refuses incomplete, non-wrapper, or gate-inconsistent evidence | Missing |
| Final `stability_report.md` or `final_stability_report.md` | Not generated for a passing final state; generator refuses incomplete, non-wrapper, or gate-inconsistent evidence | Missing |
| Default launch/config changes have evidence | Current kept changes have evidence; next `Camera.fps: 9` is documented but not applied or validated | Incomplete |

## Current failure evidence

Latest validated state remains `14_revert_preinit_inliers_35`:

| Run | stability_pass | OK ratio after init | Reset after init | Final KFs | Median inliers | Median MPs | Invalid pose publishes |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | false | 0.6352 | 13 | 21 | 112.0 | 113.0 | 0 |
| 2 | false | 0.2802 | 12 | 21 | 2.0 | 0.0 | 0 |
| 3 | false | 0.6364 | 11 | 21 | 124.0 | 125.0 | 0 |

After replay-tool enhancement, re-parsing the same logs showed `controlled_backlog_pass=true` for all three runs. That means the current primary failure evidence is not unbounded wrapper backlog; it is persistent reset/unstable tracking and one zero-map-point run.

## Next required action

When containerized ROS validation is available, apply exactly one behavior change:

```yaml
Camera.fps: 9
```

Then immediately:

1. Commit the H30 YAML change in `extra_ws/src/ORB_SLAM3_ROS2`.
2. Build `orb_slam3_ros2` inside `autoware_env_v2_host`.
3. Run the fixed-bag ROS 2 wrapper replay three times with label `15_camera_fps_9` and `--timeout-sec 210`.
4. Write replay evidence under `extra_ws/debug_runs/fix_until_stable/`.
5. Keep only if the evidence improves toward the stability gates; otherwise revert or mark the change failed.
6. If all three runs pass, generate final artifacts with `generate_final_stability_artifacts.py`; the current generator requires sync-only preflight metadata, wrapper launch commands, full-replay timeout evidence, and independently recomputed stability gates.

The goal is not complete.
