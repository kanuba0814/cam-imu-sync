# Hypothesis: Build g2o With C++11 To Match ORB

## Observation

Replay label `06_guard_debug_gravity_until_imu_init` still failed 3/3:

- `run_count=3`, `pass_count=0`, `all_passed=false`
- all runs had `imu_initialized=false`, `final_keyframes=0`
- debug gravity/scale export was cleaned up to `nan` before IMU initialization
- all runs still aborted after `New Map created with ... points`

`gdb` and `valgrind` were not available in the container, so a targeted ASAN
probe was run by preloading `libasan` only into `imu_mono_node_cpp` while
playing the bag normally.

## ASAN Evidence

ASAN reported:

```text
ERROR: AddressSanitizer: attempting free on address which was not malloc()-ed
    #1 g2o::HyperGraph::clear()
    #3 ORB_SLAM3::Optimizer::BundleAdjustment(...)
    #4 ORB_SLAM3::Optimizer::GlobalBundleAdjustemnt(...)
    #5 ORB_SLAM3::Tracking::CreateInitialMapMonocular()
```

The invalid address was allocated in `Optimizer::BundleAdjustment(...)` and
then freed by `g2o::HyperGraph::clear()` when the optimizer was destroyed.

The relevant build mismatch is:

- ORB_SLAM3 top-level `CMakeLists.txt` forces `-std=c++11`
- `Thirdparty/g2o/CMakeLists.txt` did not set a C++ standard when built
  standalone by `build.sh`
- with GCC 11, g2o can be compiled under a newer default C++ mode, while ORB
  code allocates g2o vertices/edges under C++11 Eigen aligned allocation rules

That makes the ASAN bad-free consistent with an Eigen aligned allocation/delete
ABI mismatch between ORB and g2o.

## Minimal Change

Commit `444696b` adds `-std=c++11` to g2o's standalone build flags for GCC/Clang
so g2o and ORB_SLAM3 use the same C++ standard for Eigen-aligned graph objects.

## Pending Validation

Container execution was blocked by the approval system before rebuilding after
this commit. The next validation step is:

1. rebuild `libs/ORB_SLAM3` inside `autoware_env_v2_host`
2. rebuild `extra_ws` package `orb_slam3_ros2`
3. run fixed-bag replay label `07_g2o_cpp11_abi` three times
4. verify whether the `New Map created` abort is gone and continue V2 stability
   work if reset/RECENTLY_LOST remains
