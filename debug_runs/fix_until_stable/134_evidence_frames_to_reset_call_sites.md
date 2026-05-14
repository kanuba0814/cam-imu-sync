# Evidence: `Tracking.FramesToResetIMU` call-site audit

Purpose:

- Confirm that experiment 25's `Tracking.FramesToResetIMU: 100000` change targets
  the intended ORB_SLAM3 core paths before running ROS2 wrapper replay.

Source inspected:

- `/home/gxxl/slam_ws_v2/libs/ORB_SLAM3/src/Tracking.cc`
- `/home/gxxl/slam_ws_v2/libs/ORB_SLAM3/include/Tracking.h`

Relevant call sites:

1. `TrackWithMotionModel()`
   - If IMU is initialized and
     `mCurrentFrame.mnId > mnLastRelocFrameId + mnFramesToResetIMU`, ORB_SLAM3
     calls `PredictStateIMU()` and returns immediately.
   - Otherwise it uses the visual velocity model and projection search path.

2. `TrackLocalMap()`
   - If `mCurrentFrame.mnId <= mnLastRelocFrameId + mnFramesToResetIMU`, it uses
     visual `Optimizer::PoseOptimization(&mCurrentFrame)`.
   - Once past the gate, it switches to inertial pose optimization unless the
     separate `Tracking.UseVisualPoseOptimizationBeforeInertialBA2` option is set.

3. Reset-frame gate after local map tracking
   - When `mCurrentFrame.mnId == mnLastRelocFrameId + mnFramesToResetIMU`, the
     code prints `RESETING FRAME!!!` and calls `ResetFrameIMU()`.
   - `ResetFrameIMU()` is currently a TODO/no-op stub.

Interpretation:

- `Tracking.FramesToResetIMU: 0` skips the visual recovery window and enables
  immediate IMU prediction/optimization after initialization, matching the
  experiment 24 low-inlier reset loop.
- A finite value such as `90` keeps the visual path temporarily, but reaches the
  `RESETING FRAME!!!` gate during the fixed bag, matching experiment 23 process
  deaths.
- `Tracking.FramesToResetIMU: 100000` should keep the fixed bag inside the visual
  recovery branch and keep the TODO reset-frame gate beyond the replay frame ids.

Risk to verify with replay:

- This is a targeted bypass of the unstable post-init handoff path, not proof of
  stable final behavior. The ROS2 wrapper replay must still prove all stability
  gates, especially no resets, OK ratio, final KFs, map points, inliers, runtime
  errors, and no invalid pose publishes.
