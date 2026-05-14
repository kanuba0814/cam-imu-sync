# Next Execution Manifest After Permission Restores

Superseded: this captured the pre-permission plan before experiments 20-25.
Use `141_resume_manifest_after_docker_approval.md` for the current execution
path.

## Current State
At `2026-05-15 02:50 JST`, source changes are still blocked by git/Docker
permission limits. The current wrapper repo diff is only the validated final-gate
hardening:

```text
tools/generate_final_stability_artifacts.py | 3 +++
tools/selftest_final_stability_gates.py     | 9 +++++++++
```

The H30 behavior config is not yet modified for the next experiment:

```text
Camera.fps: 9
LocalMapping.ResetOnSmallMotionBeforeInertialBA2: 0
Tracking.FramesToResetIMU: 90
ORBextractor.nFeatures: 1200
```

## Step 1: Commit Final-Gate Hardening
Run in `extra_ws/src/ORB_SLAM3_ROS2`:

```bash
git add tools/generate_final_stability_artifacts.py tools/selftest_final_stability_gates.py
git commit -m "test: require identical final replay commands"
```

This commit must contain only the two tool files above.

## Step 2: Apply One Behavior Change
Edit only:

```text
config/Monocular-Inertial/rmoncam_h30.yaml
```

Add this setting near `Tracking.FramesToResetIMU: 90`:

```yaml
# With the longer recovery window, let pre-BA2 recent-lost recovery handle
# isolated low-inlier frames instead of clearing the active map immediately.
Tracking.ResetActiveMapBeforeInertialBA2: 0
```

Then commit:

```bash
git add config/Monocular-Inertial/rmoncam_h30.yaml
git commit -m "fix: recover H30 pre-BA2 losses with longer IMU window"
```

## Step 3: Build In Container
Run from the host:

```bash
docker exec -w /home/gxxl/slam_ws_v2/extra_ws autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 colcon build --packages-select orb_slam3_ros2 --cmake-args -DORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3'
```

## Step 4: Replay Through ROS2 Wrapper
Run three full fixed-bag replays through the wrapper only:

```bash
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 20_frames90_no_pre_ba2_reset --timeout-sec 210'
```

Expected output files:

```text
extra_ws/debug_runs/fix_until_stable/20_frames90_no_pre_ba2_reset.md
extra_ws/debug_runs/fix_until_stable/20_frames90_no_pre_ba2_reset.json
extra_ws/debug_runs/fix_until_stable/20_frames90_no_pre_ba2_reset.csv
```

## Step 5: Decision
Keep the config commit only if all three runs pass:

```text
run_count=3
pass_count=3
all_passed=true
runtime_error_count=0 in every run
reset_count_after_init=0 in every run
ok_ratio_after_init >= 0.90 in every run
```

If it fails with long `RECENTLY_LOST`, low OK ratio, weak map metrics, reset
growth, or runtime errors, write an evidence file and revert the behavior commit
before trying another behavior change.
