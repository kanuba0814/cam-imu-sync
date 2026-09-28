基于固定 ros2 bag 对 ORB_SLAM3_ROS2 和 cam_imu_sync 做原则驱动诊断。注意：cam_imu_sync 包内部会启动 usb_cam 并订阅相机，所以外部 ros2 bag record 不能再订阅 /image_raw，否则会引入第二个高带宽 image subscriber，改变系统负载，导致帧率不稳定和同步失真。本任务禁止依赖 /image_raw bag。主输入只允许使用 /sync/image_raw、/sync/imu、/sync/imu_batch、/imu/pipeline_ready、/rosout。

工作区：
~/slam_ws_v2/extra_ws

bag：
~/slam_ws_v2/bags/h30_sync_only_noMove
~/slam_ws_v2/bags/h30_sync_only_normal

硬约束：
1. 不启动真实 camera driver。
2. 不启动真实 IMU driver。
3. 不启动 cam_imu_sync 实时节点。
4. 不订阅 /image_raw。
5. 不要求同一个 bag 里同时包含 raw image 和 sync image。
6. 不允许随机扫大量 ORB 参数。
7. 每一步必须先写 hypothesis，再跑验证，再写 evidence。
8. 如果证据不足，停止并说明缺哪条日志，不允许继续抽卡。

第一阶段：审计 sync-only bag。
新增 tools/h30_sync_bag_audit.py，读取 bag，输出：
debug_runs/latest/01_sync_bag_audit.md
debug_runs/latest/01_sync_bag_audit.json

必须检查：
A. bag 是否包含：
   /sync/image_raw
   /sync/imu
   /sync/imu_batch
   /imu/pipeline_ready
   /rosout

B. 不允许要求 bag 包含 /image_raw。
   如果代码里发现还要求 /image_raw，修正审计逻辑。

C. 统计：
   /sync/image_raw 消息数
   /sync/imu 消息数
   /sync/imu_batch 消息数
   /sync/image_raw 频率
   /sync/imu 频率
   /sync/image_raw header.stamp 单调性
   /sync/imu header.stamp 单调性
   /sync/imu period mean/std

D. 对每帧 /sync/image_raw，寻找最近的 /sync/imu。
   输出 image_stamp - nearest_imu_stamp 的 min/p50/p95/max。
   判断 /sync/image_raw + /sync/imu 是否已经是对齐后的时间域。
   如果已经对齐，则 ORB wrapper 内 cam_imu_time_offset 应为 0.0。
   如果 p50 接近 ±15ms，说明 sync 输出 header 语义还没有真正对齐，需要回查 sync 包内部 stamp 逻辑。

E. 检查 /sync/imu 的单位：
   静止段 0–15s：
   acc_norm_mean 应接近 9.8 m/s^2。
   gyro_norm_mean 应接近 0 rad/s。
   如果 acc_norm 接近 1，说明加速度可能仍是 g。
   如果 gyro 动态段数值像 deg/s，说明角速度可能未转 rad/s。

第一阶段停止条件：
如果 /sync/image_raw 或 /sync/imu 频率明显异常，或者 header.stamp 非单调，停止，不跑 ORB。
如果 IMU 单位明显错误，停止，修 yesense_ros2 或 cam_imu_sync 输出，不跑 ORB。

第二阶段：只验证单目图像能力。
新增或修改 ORB_SLAM3_ROS2/launch/h30_bag_replay.launch.py。
该 launch 只能启动 ORB wrapper 和可选 ros2 bag play，不启动真实硬件。
参数必须包括：
bag_path
play_bag
sensor_type
image_topic
imu_topic
settings_file
cam_imu_time_offset
orb_time_offset_mode
debug_enable
use_rviz
use_pangolin
rate
duration

运行：
sensor_type=monocular
image_topic=/sync/image_raw
settings_file=ORB_SLAM3_ROS2/config/Monocular/rmoncam.yaml
cam_imu_time_offset=0.0

输出：
debug_runs/latest/02_mono_sync_image.md

必须报告：
- 是否进入 OK
- first_ok_time
- LOST 次数
- keyframe 数
- tracked map points 中位数
- inlier 数中位数

停止条件：
如果单目失败，不进入 VI。先检查图像编码、Camera.RGB、内参、畸变、ORB 特征数。不要调 IMU。

第三阶段：只验证 sync 输出是否应使用 offset=0。
只跑两组，不允许大矩阵。

实验 3A：
sensor_type=imu-monocular
image_topic=/sync/image_raw
imu_topic=/sync/imu
settings_file=ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml
cam_imu_time_offset=0.0
orb_time_offset_mode=zero_for_sync

实验 3B：
sensor_type=imu-monocular
image_topic=/sync/image_raw
imu_topic=/sync/imu
settings_file=ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml
cam_imu_time_offset=-0.01574
orb_time_offset_mode=legacy_warn

输出：
debug_runs/latest/03_sync_offset_test.md

必须比较：
- imu_initialized
- first_imu_initialized_time
- OK ratio
- reset_count
- insufficient_imu_count
- image_to_last_imu_ms p50/p95
- median inliers
- keyframe count

判断：
如果 3A 明显优于 3B，认定 /sync/image_raw + /sync/imu 已经对齐，h30_sync_slam.launch.py 和 h30_sync_debug_slam.launch.py 默认应改为：
cam_imu_time_offset=0.0
orb_time_offset_mode=zero_for_sync

如果 3B 明显优于 3A，说明 /sync 输出的 header stamp 语义不是“已对齐”，需要检查 cam_imu_sync 内部 stamp 写法。

如果 3A/3B 都失败，但单目成功，进入 Tbc/IMU 语义检查，不允许直接扫 ORB 参数。

第四阶段：检查 Tbc/Tcb 方向。
从 ORB_SLAM3 源码确认 settings 文件里读取的 Tbc 到底表示：
- camera 到 IMU
- IMU 到 camera
- body 到 camera
- camera 到 body

输出：
debug_runs/latest/04_tbc_semantics.md

必须包含：
- rmoncam_h30.yaml 里的矩阵
- ORB_SLAM3 源码读取位置
- wrapper 是否额外做坐标变换
- 当前 Kalibr 结果方向是否需要取逆
- 如果需要取逆，只生成临时 yaml 验证，不直接覆盖原文件

第五阶段：只有时间戳、IMU单位、单目、offset、Tbc 都没有硬错误，才允许轻量测试 ORBextractor。
最多三组临时 yaml：
- nFeatures=800, iniThFAST=15, minThFAST=5
- nFeatures=1200, iniThFAST=15, minThFAST=5
- nFeatures=1500, iniThFAST=15, minThFAST=5

不允许同时改 RGB、FAST、IMU noise。
不允许大矩阵抽卡。

最终交付：
debug_runs/latest/decision.md

decision.md 必须给出唯一结论：
1. sync bag 本身无效，原因是……
2. sync image 单目无法建图，原因是……
3. sync topic 已对齐，ORB wrapper 二次 offset 是主因。
4. sync topic 没有真正对齐，cam_imu_sync header 语义错误。
5. IMU 单位错误。
6. Tbc/Tcb 方向错误。
7. QoS/回放导致 IMU 没进入 ORB。
8. 上述全部排除后，ORBextractor 特征数过低是主要原因。

额外要求：
如果需要 raw image 与 sync image 的关系，不允许通过 ros2 bag record /image_raw 获取。
必须在 cam_imu_sync 节点内部增加低带宽 debug trace，例如每帧输出：
raw_image_stamp
published_sync_image_stamp
selected_imu_stamp_before
selected_imu_stamp_after
sync_offset_ms
imu_count_used
image_queue_size
imu_queue_size
dropped_image_count
dropped_imu_count

这个 trace 可以写 CSV 或发布低带宽 debug topic，但不能新增第二个 /image_raw subscriber。