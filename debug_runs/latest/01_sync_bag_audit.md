# 01 Sync Bag Audit

- output_root: `/home/gxxl/slam_ws_v2/extra_ws/debug_runs`
- main_bag: `/home/gxxl/slam_ws_v2/bags/h30_sync_only_normal`
- static_bag: `/home/gxxl/slam_ws_v2/bags/h30_sync_only_noMove`
- overall_status: **PASS**
- raw_image_requirement: `/image_raw` is intentionally not required or read

## Hypothesis

The sync-only bags are valid inputs if `/sync/image_raw` is near 30Hz, `/sync/imu` is near 100Hz, both header stamps are monotonic, and static IMU units look like m/s^2 plus rad/s. If image-to-nearest-IMU p50 is near zero, the ORB wrapper should use `cam_imu_time_offset=0.0` for these sync topics.

## Evidence

### Main Bag

- bag_name: `h30_sync_only_normal`
- bag_path: `/home/gxxl/slam_ws_v2/bags/h30_sync_only_normal`
- status: **PASS**
- failures: `[]`
- warnings: `['/sync/imu_batch present_but_empty', '/imu/pipeline_ready present_but_empty']`

#### Topic Presence And Timing

| Topic | Metadata | Count | Type | Header First | Header Last | Rate Hz | Period Mean ms | Period Std ms | Monotonic | NaNs | Extra |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| `/sync/image_raw` | True | 5396 | `sensor_msgs/msg/Image` | 1778734779.148 | 1778734958.910 | 30.012 | 33.320 | 1.890 | True | 0 | {'yuv422_yuy2': 5396} {'640x480@step1280': 5396} |
| `/sync/imu` | True | 17978 | `sensor_msgs/msg/Imu` | 1778734779.161 | 1778734958.951 | 99.989 | 10.001 | 0.149 | True | 0 |  |
| `/sync/imu_batch` | True | 0 | `sensor_msgs/msg/Imu` |  |  |  |  |  | True | 0 |  |
| `/imu/pipeline_ready` | True | 0 | `std_msgs/msg/Bool` |  |  |  |  |  | True | 0 | {} |
| `/rosout` | True | 50 | `rcl_interfaces/msg/Log` |  |  | 0.277 |  |  | True | 0 | levels={'20': 48, '30': 2} names={'cam_imu_sync_node': 40, 'rosbag2_recorder': 10} |

#### Sync Time-Domain Check

| Metric | Count | Min ms | P50 ms | P95 ms | Max ms | Interpretation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `sync_image_minus_nearest_sync_imu` | 5396 | -14.862 | -0.289 | 3.956 | 5.000 | aligned_time_domain_offset_should_be_0 |

#### Static IMU Unit Check

| Topic | Samples | Mean Acc XYZ | Acc Norm Mean | Acc Norm Std | Acc Norm P95 | Mean Gyro XYZ | Gyro Norm Mean | Gyro Norm Std | Gyro Norm P95 | Unit Hint |
| --- | ---: | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| `/sync/imu` | 1501 | [9.74360537937955, -0.3595004235622058, -0.18313069886121283] | 9.752043 | 0.027328 | 9.773483 | [-0.0005917359321209966, -0.00043195225377672347, 0.0012355866586115812] | 0.004045 | 0.002922 | 0.009727 | acc_mps2_like,static_gyro_radps_like |
| `/sync/imu_batch` | 0 |  |  |  |  |  |  |  |  | no_samples |

### Static Bag

- bag_name: `h30_sync_only_noMove`
- bag_path: `/home/gxxl/slam_ws_v2/bags/h30_sync_only_noMove`
- status: **PASS**
- failures: `[]`
- warnings: `['/sync/imu_batch present_but_empty', '/imu/pipeline_ready present_but_empty']`

#### Topic Presence And Timing

| Topic | Metadata | Count | Type | Header First | Header Last | Rate Hz | Period Mean ms | Period Std ms | Monotonic | NaNs | Extra |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| `/sync/image_raw` | True | 594 | `sensor_msgs/msg/Image` | 1778734689.888 | 1778734709.644 | 30.017 | 33.314 | 1.932 | True | 0 | {'yuv422_yuy2': 594} {'640x480@step1280': 594} |
| `/sync/imu` | True | 1980 | `sensor_msgs/msg/Imu` | 1778734689.891 | 1778734709.681 | 100.000 | 10.000 | 0.000 | True | 0 |  |
| `/sync/imu_batch` | True | 0 | `sensor_msgs/msg/Imu` |  |  |  |  |  | True | 0 |  |
| `/imu/pipeline_ready` | True | 0 | `std_msgs/msg/Bool` |  |  |  |  |  | True | 0 | {} |
| `/rosout` | True | 47 | `rcl_interfaces/msg/Log` |  |  | 2.818 |  |  | True | 0 | levels={'20': 45, '30': 2} names={'cam_imu_sync_node': 23, 'yesense_pub': 13, 'usb_cam': 10, 'rosbag2_recorder': 1} |

#### Sync Time-Domain Check

| Metric | Count | Min ms | P50 ms | P95 ms | Max ms | Interpretation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `sync_image_minus_nearest_sync_imu` | 594 | -4.979 | 0.602 | 4.642 | 4.999 | aligned_time_domain_offset_should_be_0 |

#### Static IMU Unit Check

| Topic | Samples | Mean Acc XYZ | Acc Norm Mean | Acc Norm Std | Acc Norm P95 | Mean Gyro XYZ | Gyro Norm Mean | Gyro Norm Std | Gyro Norm P95 | Unit Hint |
| --- | ---: | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| `/sync/imu` | 1501 | [9.743245855839131, -0.3531340297856029, -0.1958183343052636] | 9.751722 | 0.078069 | 9.772001 | [-0.0005321185785647142, -0.0005284688272038278, 0.0014055861291044167] | 0.003979 | 0.004051 | 0.007906 | acc_mps2_like,static_gyro_radps_like |
| `/sync/imu_batch` | 0 |  |  |  |  |  |  |  |  | no_samples |

## Stage-1 Gate

- result: **PASS**
- stop_reason: `none`
- next_step: run stage 2 monocular sync-image validation
