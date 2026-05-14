# Completion Audit: experiment 25 not yet validated

## Objective Restatement

Use `goal/orbDebugGoalV2.md` to fix H30 sync-only ROS2 bag stability through the
ROS2 wrapper path. The goal is complete only after a fixed-bag, full-length,
three-run `orb_slam3_ros2` replay aggregate passes all stability gates and the
final artifacts are generated from that passing aggregate.

## Prompt-to-Artifact Checklist

| Requirement | Current evidence | Status |
| --- | --- | --- |
| Protect git state and keep source changes committed | wrapper repo HEAD is `61d405e fix: keep H30 visual recovery beyond fixed replay`; core repo HEAD is `a5ea5b1 fix: allow delaying monocular IMU initialization` | Covered |
| One minimal explainable change in current round | `131_hypothesis_visual_recovery_window_full_bag.md` documents the `Tracking.FramesToResetIMU: 100000` hypothesis | Covered |
| Default config points to the tested candidate | installed H30 config resolves to source `config/Monocular-Inertial/rmoncam_h30.yaml` and contains `LocalMapping.ImuMonoInitMinTime: 4.0`, `Tracking.FramesToResetIMU: 100000` | Covered for candidate |
| Use latest fixed bag | `bags/LATEST_BAG.txt` resolves to `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136` | Covered |
| Sync-only replay, no `/image_raw` dependency | `run_stability_replay.py --preflight-only` selected `/sync/image_raw,/sync/imu` and ignored `/image_raw, /imu/data_raw, /imu/raw_hw` | Covered by preflight |
| Replay starts at beginning of bag | preflight reported `start_offset_sec: 0.0`; harness rejects non-zero start offsets | Covered by preflight |
| ROS2 wrapper path only | final generator requires `ros2 launch orb_slam3_ros2 h30_bag_replay.launch.py`; user explicitly reminded wrapper validation is mandatory | Gate covered, replay not yet run |
| Build inside `autoware_env_v2_host` | attempted `docker exec ... colcon build --packages-select orb_slam3_ros2 ...` | Blocked by approval usage limit |
| Three consecutive full ROS2 wrapper replays | planned label `25_visual_recovery_window_full_bag_4s` | Missing |
| IMU init success in all final runs | no experiment 25 aggregate yet | Missing |
| `reset_count` no increase after init | no experiment 25 aggregate yet | Missing |
| OK ratio after init >= 0.90 | no experiment 25 aggregate yet | Missing |
| No long `RECENTLY_LOST` / `LOST` | no experiment 25 aggregate yet | Missing |
| No active map reset in final 60 seconds | no experiment 25 aggregate yet | Missing |
| final keyframes >= 20 | no experiment 25 aggregate yet | Missing |
| median map points >= 80 | no experiment 25 aggregate yet | Missing |
| median inliers >= 50 | no experiment 25 aggregate yet | Missing |
| sane IMU lag | parser gate requires `abs(image_to_last_imu_ms.p95) <= 20.0`; no experiment 25 aggregate yet | Missing |
| processed image age p95 < 150 ms | parser gate covers it; no experiment 25 aggregate yet | Missing |
| controlled backlog | parser gate covers ORB FPS, image age, and image buffer max; no experiment 25 aggregate yet | Missing |
| no fake pose publishes | parser gate requires `invalid_pose_publish_count == 0`; no experiment 25 aggregate yet | Missing |
| no runtime errors | parser gate requires `runtime_error_count == 0`; no experiment 25 aggregate yet | Missing |
| Final artifacts | `generate_final_stability_artifacts.py` writes all required files only from a fully passing aggregate | Missing |

## Tooling Checks Completed

- `python3 -m py_compile` passed for replay/parser/final-generator/selftest tools.
- `tools/selftest_final_stability_gates.py` passed.
- `run_stability_replay.py --preflight-only` passed for experiment 25.

## Blocker

The required container command is still rejected by the approval reviewer:

```text
You've hit your usage limit. To get more access now, send a request to your admin or try again at 10:28 AM.
```

This is not a build failure and not a replay result. Do not mark the goal
complete until container build and three ROS2 wrapper replays run and pass.

## Next Command When Approval Returns

```bash
docker exec -w /home/gxxl/slam_ws_v2/extra_ws autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 colcon build --packages-select orb_slam3_ros2 --cmake-args -DORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3'
```

Then:

```bash
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 25_visual_recovery_window_full_bag_4s --timeout-sec 210'
```
