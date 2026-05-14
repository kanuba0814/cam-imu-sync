# Evidence: revert pre-init inlier gate change

## Change under validation

- `extra_ws/src/ORB_SLAM3_ROS2` commit: `7a5fe5d Revert "fix: lower H30 preinit inlier gate"`
- Removed failed config:
  - `Tracking.MinInliersImuMonoPreInit: 35`
- Remaining useful config:
  - `LocalMapping.ResetOnSmallMotionBeforeInertialBA2: 0`

## Validation

Rebuilt `orb_slam3_ros2` in `autoware_env_v2_host`, then ran:

```bash
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 14_revert_preinit_inliers_35 --timeout-sec 180'
```

## Result

- `pass_count`: 0 / 3
- run return codes: 124, 124, 124
- required V2 tags present: true for all three runs
- IMU initialized: true for all three runs
- invalid pose publishes: 0 for all three runs

| Run | OK ratio after init | Reset after init | Final KFs | Median inliers | Median MPs | Max lost streak |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.6352 | 13 | 21 | 112.0 | 113.0 | 0.00s |
| 2 | 0.2802 | 12 | 21 | 2.0 | 0.0 | 0.00s |
| 3 | 0.6364 | 11 | 21 | 124.0 | 125.0 | 0.00s |

## Interpretation

The revert is beneficial and should be kept. It restores two high-map-point runs and removes the all-zero median map-point regression from `13_preinit_inliers_35`.

The system is still not stable: reset count remains above the goal, OK ratio remains below 0.90, and one run still collapses to zero median tracked map points. The wrapper gate continues to block bad poses, and queue/latency metrics remain bounded.

The next minimal hypothesis should target a timing mismatch. The H30 YAML still declares `Camera.fps: 30`, while runtime summaries in the ROS 2 replay show ORB processing mostly around 7-12 FPS on this bag. ORB-SLAM3 derives internal frame windows from camera FPS, including recent-relocalization and keyframe timing, so the mismatch may be extending reset-sensitive windows beyond the actual replay cadence.
