# Resume Manifest: after Docker approval returns

Current blocker:

- `docker exec` was rejected by the approval reviewer due usage limit.
- Last checked at `2026-05-15 06:58 JST`, before the retry window reported as
  `10:28 AM`.

Do not change behavior before executing this sequence. The current candidate is
already committed:

- wrapper: `61d405e fix: keep H30 visual recovery beyond fixed replay`
- ORB core: `a5ea5b1 fix: allow delaying monocular IMU initialization`
- evidence: `debug_runs/fix_until_stable/100_...` through `142_...`

## 1. Build wrapper in the authoritative ROS2 container

```bash
docker exec -w /home/gxxl/slam_ws_v2/extra_ws autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 colcon build --packages-select orb_slam3_ros2 --cmake-args -DORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3'
```

Expected minimum:

- `orb_slam3_ros2` build succeeds inside `autoware_env_v2_host`.
- Do not substitute a host build for this check.

## 2. Run experiment 25 three-run ROS2 wrapper replay

```bash
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 25_visual_recovery_window_full_bag_4s --timeout-sec 210'
```

Expected artifacts:

- `extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s.md`
- `extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s.csv`
- `extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s.json`
- `extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s_run01.log`
- `extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s_run02.log`
- `extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s_run03.log`

## 3. Triage aggregate and logs

```bash
sed -n '1,220p' extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s.md
sed -n '1,120p' extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s.csv
jq '{label, run_count, pass_count, all_passed, runs: [.runs[] | {run_index, returncode, stability_pass, errors, first_imu_initialized_frame, ok_ratio_after_init, max_lost_streak_sec_after_init, reset_count_after_init, reset_delta_last_60_sec, final_keyframes, median_inliers_after_init, median_tracked_map_points_after_init, runtime_error_count, record_counts}]}' extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s.json
```

```bash
rg -n "frames_to_reset_imu|imu_mono_init_min_time|RESETING FRAME|process has died|runtime_error|TRACK_LOCAL_MAP_FAILED|ACTIVE_MAP_RESET|RECENTLY_LOST|LOST|IMU_INIT_START|IMU_INIT_SUCCESS|IMU_INIT_FAIL|orb_state_transition|orb_pose_gate" \
  extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s_run01.log \
  extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s_run02.log \
  extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s_run03.log
```

Mandatory first log confirmation:

- `frames_to_reset_imu=100000`
- `imu_mono_init_min_time=4`

## 4. If all three runs pass

Run the generator command in:

- `extra_ws/debug_runs/fix_until_stable/135_next_final_artifact_command_after_pass.md`

Then inspect:

```bash
sed -n '1,240p' extra_ws/debug_runs/fix_until_stable/final_stability_report.md
sed -n '1,220p' extra_ws/debug_runs/fix_until_stable/decision.md
sed -n '1,220p' extra_ws/debug_runs/fix_until_stable/final_patch_summary.md
sed -n '1,220p' extra_ws/debug_runs/fix_until_stable/final_commands.md
cmp -s \
  extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml \
  extra_ws/debug_runs/fix_until_stable/best_config.yaml
```

Only after this, perform the completion audit against `goal/orbDebugGoalV2.md`.

## 5. If any run fails

Do not generate final artifacts and do not mark the goal complete.

Use:

- `extra_ws/debug_runs/fix_until_stable/136_next_experiment25_triage_after_replay.md`

Then make exactly one next behavior change, with:

1. a new hypothesis file,
2. one focused source/config commit,
3. container build,
4. three-run ROS2 wrapper replay.
