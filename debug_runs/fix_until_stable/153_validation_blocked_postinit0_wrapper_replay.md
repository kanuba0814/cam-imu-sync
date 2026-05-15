# Validation Blocked: Post-Init 0 Wrapper Replay

## Current Candidate

- Wrapper repo commit: `f93a5c7 fix: allow H30 post-init visual dropout survival`
- Evidence/hypothesis commit: `6ce5de8 debug: record H30 zero-inlier survival hypothesis`
- Config under test: `Tracking.MinInliersImuMonoPostInit: 0`
- Wrapper trust gates remain unchanged:
  - `min_pose_publish_inliers=15`
  - `min_pose_publish_tracked_mappoints=15`

## Required Validation

The goal is not satisfied until this candidate completes:

1. Containerized `colcon build --packages-select orb_slam3_ros2`.
2. Three full fixed-bag ROS2 wrapper replays with label
   `30_postinit_inliers0_wrapper_pose_gate_full_window`.
3. All three replays pass the final stability gates.

No `30_postinit_inliers0_wrapper_pose_gate_full_window*` artifacts existed at
the time of this audit, so no validation result can be claimed.

## Blocker

The required `docker exec` validation path is temporarily blocked by the
execution approval system before the reported retry time. The workspace rule
requires ROS2 build/run validation inside `autoware_env_v2_host`; using the host
ROS environment or ORB standalone would not satisfy the objective.

## Next Command

Run this build first:

```bash
docker exec -w /home/gxxl/slam_ws_v2/extra_ws autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 colcon build --packages-select orb_slam3_ros2 --cmake-args -DORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3'
```

Then run the wrapper replay:

```bash
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 30_postinit_inliers0_wrapper_pose_gate_full_window --timeout-sec 210'
```
