# SLAM Debug Run Summary - 2026-05-08 18:45

## 结论

本次约一分钟运行没有生成新增的结构化 debug CSV。工作区里没有发现：

- `extra_ws/logs/slam_debug/**/raw_imu.csv`
- `extra_ws/logs/slam_debug/**/sync_frames.csv`
- `extra_ws/logs/slam_debug/**/sync_resampled_imu.csv`
- `extra_ws/logs/slam_debug/**/orb_track.csv`
- `extra_ws/logs/slam_debug/**/orb_pose.csv`
- `extra_ws/logs/slam_debug/**/summary_1hz*.csv`

今天实际新增的是 ORB-SLAM3 默认 output 目录，其中两个 MP4 都只有 258 bytes，`ffprobe` 显示 `duration=N/A`。这说明 ORB node 启动过并创建了输出目录，但没有写入有效视频帧，也没有开启/走到新增 debug 记录链。

## 本次发现的输出

| 路径 | 修改时间 | 结果 |
| --- | --- | --- |
| `extra_ws/src/ORB_SLAM3_ROS2/output/2026-05-08_18-44-21/video/2026-05-08_18-44-21.mp4` | 2026-05-08 18:45:09 JST | 258 bytes, `duration=N/A` |
| `extra_ws/src/ORB_SLAM3_ROS2/output/2026-05-08_18-45-18/video/2026-05-08_18-45-18.mp4` | 2026-05-08 18:47:16 JST | 258 bytes, `duration=N/A` |

`cloud/` 和 `grid/` 目录为空；没有 `.pcd`、map 或 pose/debug CSV 输出。

## 判断

最可能原因是运行命令没有带 `debug_enable:=true`，或者运行的 launch 不是新增参数后的安装版本。由于没有 `orb_track.csv` 和 `sync_frames.csv`，本次无法从日志中直接判断：

- ORB 实际 `TrackMonocular` 图像时间
- 每帧 IMU 数量和 IMU 窗口
- 图像时间到最后 IMU 的差
- `/sync/imu` 实际频率
- ORB YAML `IMU.Frequency` 与实际频率是否一致
- pose 静止漂移量
- gyro/acc 静止均值
- 是否对已同步图像再次加 offset

## 下一次建议命令

先确保使用容器内已安装的新版本：

```bash
docker exec -it autoware_env_v2_host bash
source /opt/ros/humble/setup.bash
source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash
source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash
```

Terminal 1:

```bash
ros2 launch cam_imu_sync cam_imu_sync.launch.py \
  debug_enable:=true \
  debug_run_id:=static_60s_$(date +%Y%m%d_%H%M%S) \
  debug_expected_imu_rate_hz:=100.0
```

Terminal 2 使用同一个 `debug_run_id`：

```bash
ros2 launch orb_slam3_ros2 h30_sync_slam.launch.py \
  debug_enable:=true \
  debug_run_id:=<same_run_id> \
  debug_expected_imu_rate_hz:=100.0 \
  orb_time_offset_mode:=legacy_warn
```

完成后应看到：

```text
extra_ws/logs/slam_debug/<same_run_id>/
  raw_imu.csv
  sync_frames.csv
  sync_resampled_imu.csv
  orb_track.csv
  orb_pose.csv
  summary_1hz.csv
  summary_1hz_orb.csv
  summary_1hz_yesense.csv
  run_meta_*.json
```

