# 04 Public Transform Header Precheck

## Hypothesis

The wrapper included the generated internal header:

```cpp
#include <geometry_msgs/msg/detail/transform_stamped__struct.hpp>
```

That can be brittle across ROS 2 installs. The public C++ header is:

```cpp
#include <geometry_msgs/msg/transform_stamped.hpp>
```

Using the public header should preserve behavior while reducing the chance of a container build failure.

## Minimal Change

`extra_ws/src/ORB_SLAM3_ROS2/src/imu_mono_realsense.cpp` now includes `geometry_msgs/msg/transform_stamped.hpp` instead of the generated `detail` header.

## Commit

`extra_ws/src/ORB_SLAM3_ROS2`:

```text
4b7ba06 fix: use public TransformStamped ROS header
```

## Local Validation

```bash
git -C extra_ws/src/ORB_SLAM3_ROS2 diff --check
python3 -m py_compile \
  extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py \
  extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py
```

Both commands passed.

## Remaining Gate

This does not replace the required containerized build and three replay validations. Docker access is still required for the next acceptance step.
