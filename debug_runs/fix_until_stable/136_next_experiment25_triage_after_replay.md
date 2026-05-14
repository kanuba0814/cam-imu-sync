# Next: experiment 25 triage after ROS2 wrapper replay

Use this immediately after running:

```bash
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 25_visual_recovery_window_full_bag_4s --timeout-sec 210'
```

## First checks

```bash
sed -n '1,220p' extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s.md
sed -n '1,120p' extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s.csv
jq '{label, run_count, pass_count, all_passed, runs: [.runs[] | {run_index, returncode, stability_pass, errors, first_imu_initialized_frame, ok_ratio_after_init, max_lost_streak_sec_after_init, reset_count_after_init, reset_delta_last_60_sec, final_keyframes, median_inliers_after_init, median_tracked_map_points_after_init, runtime_error_count, record_counts}]}' extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s.json
```

## Log pattern scan

```bash
rg -n "frames_to_reset_imu|imu_mono_init_min_time|RESETING FRAME|process has died|runtime_error|TRACK_LOCAL_MAP_FAILED|ACTIVE_MAP_RESET|RECENTLY_LOST|LOST|IMU_INIT_START|IMU_INIT_SUCCESS|IMU_INIT_FAIL|orb_state_transition|orb_pose_gate" \
  extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s_run01.log \
  extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s_run02.log \
  extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s_run03.log
```

## If all three pass

1. Run the final artifact command from
   `135_next_final_artifact_command_after_pass.md`.
2. Inspect `final_stability_report.md`, `decision.md`,
   `final_patch_summary.md`, `final_commands.md`, and compare
   `best_config.yaml` against the H30 source config.
3. Perform the completion audit required by `goal/orbDebugGoalV2.md` before
   calling the goal complete.

## If any run fails

Do not generate final artifacts. Choose exactly one next branch:

- Runtime error or process death:
  - If `RESETING FRAME!!!` still appears, the high frame window did not load or
    frame ids exceeded the assumed window; verify the loaded settings path and
    `frames_to_reset_imu=100000` log first.
  - If death occurs without the reset-frame gate, inspect shutdown/timer/ORB
    access logs before changing tracking behavior.

- Reset loop after IMU initialization:
  - Compare reset frame ids with `IMU_INIT_SUCCESS` frame ids.
  - If resets occur while the visual branch is active, the failure is no longer
    immediate IMU prediction handoff; inspect `TRACK_LOCAL_MAP_FAILED` reasons
    and visual quality/inlier counts.

- IMU initialization too late or final KFs below 20:
  - The 4 second bootstrap delay may be over-conservative for some runs.
  - Do not change it together with the frame window; test a single
    `LocalMapping.ImuMonoInitMinTime` value only after documenting the evidence.

- OK ratio below 0.90 with no resets:
  - Inspect `max_lost_streak_sec_after_init`, state transitions, and inlier/map
    point medians to decide whether this is short intermittent loss or long
    recent-loss behavior.

- Missing V2 tags or replay metadata:
  - Treat as instrumentation/replay harness failure, not as SLAM stability
    evidence.

Every next behavior change must get a new hypothesis file, one focused commit,
container build, and three-run ROS2 wrapper replay.
