# 04 Tbc Semantics

## Hypothesis

If ORB-SLAM3 expects camera-to-body/IMU but the YAML contains body/IMU-to-camera, visual-inertial initialization can fail even when timestamps and units are plausible. The check must use source code semantics, not variable names alone.

## rmoncam_h30.yaml Matrix

`/home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml` currently sets:

```text
IMU.T_b_c1:
[-0.00921317, -0.99956084,  0.02816470,  0.01201772,
 -0.99988960,  0.00888051, -0.01191356,  0.00097831,
  0.01165821, -0.02827136, -0.99953230, -0.06867033,
  0.0,         0.0,         0.0,         1.0]
```

The inverse is:

```text
[-0.00921317, -0.99988959,  0.01165821,  0.00188950,
 -0.99956083,  0.00888051, -0.02827135,  0.01006235,
  0.02816471, -0.01191356, -0.99953230, -0.06896503,
  0.0,         0.0,         0.0,         1.0]
```

## Source Evidence

- `libs/ORB_SLAM3/src/Settings.cc` reads `IMU.T_b_c1` into `Tbc_`.
- `libs/ORB_SLAM3/src/Tracking.cc` passes `settings->Tbc()` into `new IMU::Calib(...)`.
- `libs/ORB_SLAM3/src/ImuTypes.cc` stores `mTbc = sophTbc` and computes `mTcb = mTbc.inverse()`.
- `libs/ORB_SLAM3/src/Frame.cc` computes camera pose from body pose as `mTcw = mImuCalib.mTcb * Tbw`.

That chain means ORB's `Tbc` is camera-to-body/IMU; its inverse `Tcb` is body/IMU-to-camera.

## Kalibr Direction

Kalibr E52 report:

```text
T_ci: (imu0 to cam0)
[-0.00921317, -0.9998896, 0.01165821, 0.0018895, ...]

T_ic: (cam0 to imu0)
[-0.00921317, -0.99956084, 0.0281647, 0.01201772, ...]
```

The camchain file names `T_cam_imu`, but its matrix equals the report's `T_ci` / IMU-to-camera. The current ORB YAML does not use that camchain matrix directly; it uses the report's `T_ic` / camera-to-IMU.

## Wrapper Transform Check

`imu_mono_realsense.cpp` does not apply any extra camera/IMU extrinsic transform before `TrackMonocular`. It only optionally reorders/scales raw IMU vector components, then passes:

```cpp
ORB_SLAM3::IMU::Point(acc, gyr, tIMU)
orb_slam3_system_->TrackMonocular(imageFrame, tIm, vImuMeas)
```

The later TF/odom publishing logic transforms ORB output for ROS visualization, not the IMU measurement frame used by ORB initialization.

## Gate

No Tbc/Tcb hard error found. The current YAML direction is consistent with ORB-SLAM3's camera-to-body expectation. No inverse YAML was generated because the evidence does not justify changing Tbc direction.
