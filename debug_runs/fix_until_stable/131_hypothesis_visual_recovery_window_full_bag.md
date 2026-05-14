# Hypothesis: keep H30 visual recovery window beyond full fixed bag

Current committed source/config change:

- wrapper repo commit: `61d405e fix: keep H30 visual recovery beyond fixed replay`
- changed file: `config/Monocular-Inertial/rmoncam_h30.yaml`
- changed key: `Tracking.FramesToResetIMU: 100000`

Observed prior failure mechanisms:

- `Tracking.FramesToResetIMU: 90` preserved the visual recovery path after IMU initialization, and one run reached `OK ratio=1.0` with `reset_after_init=0`, but the finite frame gate later triggered `RESETING FRAME!!!` and wrapper process death.
- `Tracking.FramesToResetIMU: 0` removed the wrapper process death, but switched immediately to IMU prediction after initialization and caused repeated post-init low-inlier active-map resets.

Hypothesis:

- A very large `Tracking.FramesToResetIMU` will keep the fixed H30 ROS2 wrapper replay in the visual recovery path for the full bag, avoiding both the incomplete finite reset-frame gate and the unstable immediate IMU-prediction handoff.

Required validation:

- Build `orb_slam3_ros2` inside `autoware_env_v2_host`.
- Run the fixed sync-only bag through `orb_slam3_ros2` ROS2 wrapper exactly three times with full replay and `start_offset_sec=0.0`.
- Accept only if all three runs satisfy the V2 stability gates: IMU init, no reset increase after init, OK ratio >= 0.90, no long LOST/RECENTLY_LOST, no reset in final 60 seconds, final KFs >= 20, median MPs >= 80, median inliers >= 50, sane IMU lag, processed image age p95 < 150 ms, controlled backlog, no invalid pose publish, and no runtime errors.

Current blocker:

- `docker exec` is currently blocked by the execution approval reviewer due a usage limit, so the required container build/replay validation has not run yet.
