修复 ORB_SLAM3_ROS2 + ORB_SLAM3 在 H30 sync-only ros2 bag 上运行卡顿、持续 reset、几乎无法稳定建图定位的问题。本目标不是只解释失败原因，而是必须形成“诊断 → 修改 → 编译 → 离线 bag 回放验证 → 若失败继续定位和修改”的闭环，直到固定 bag 上达到稳定建图和定位标准。所有源码改动必须保留 git 痕迹，每个 commit 必须单一目的、可回滚、commit message 清楚说明修改原因。

工作区：
~/slam_ws_v2/extra_ws

bag：
从 ~/slam_ws_v2/bags/LATEST_BAG.txt 读取主 bag。
bag 是 sync-only bag，只允许依赖：
/sync/image_raw
/sync/imu
/sync/imu_batch
/imu/pipeline_ready
/rosout

重要背景：
cam_imu_sync 包内部会启动 usb_cam 并订阅相机。外部 ros2 bag record 不能再订阅 /image_raw，否则会引入第二个高带宽 image subscriber，破坏同步链路。因此本目标禁止要求 bag 包含 /image_raw，禁止通过订阅 /image_raw 做诊断。

硬约束：
1. 不允许启动真实 camera driver。
2. 不允许启动真实 IMU driver。
3. 不允许启动实时 cam_imu_sync 节点做无控制测试。
4. 不允许订阅 /image_raw。
5. 不允许把 imu_initialized=true 当作成功。
6. 不允许把“解释了问题”当作完成。
7. 不允许随机扫大矩阵。
8. 每轮必须先写 hypothesis，再改动，再运行验证，再写 evidence。
9. 每个源码改动必须 git commit。
10. 如果一个改动无效，必须明确保留为 debug instrumentation，或者 revert，不能堆叠不可解释修改。
11. 最终必须在固定 bag 上达到稳定建图定位标准，否则不能声明完成。

稳定成功标准：
必须全部满足：

A. 离线 bag 回放至少连续 3 次通过。
B. 每次运行中：
   - IMU 初始化成功。
   - 初始化成功后 reset_count 不再增加。
   - 初始化成功后 tracking OK ratio >= 0.90。
   - 初始化成功后不能长时间 RECENTLY_LOST 或 LOST。
   - 最后 60 秒不能发生 active map reset。
   - final keyframes >= 20。
   - median tracked map points >= 80。
   - median inliers >= 50。
   - image_to_last_imu_ms p50/p95 没有异常跳变。
   - processed_image_age_ms p95 < 150ms，不能持续处理旧帧。
   - img_buf_size 不能持续增长。
   - ORB processed fps 或受控丢帧机制必须稳定，不能无限 backlog。
   - LOST / RECENTLY_LOST / NOT_INITIALIZED 状态下不得继续发布新的 odom/tf 假定位。
C. 生成最终 best_config.yaml、decision.md、stability_report.md。
D. 最终默认 launch/config 的修改必须有明确证据支持。

第一阶段：保护 git 状态并建立修复分支。
执行：
- git status --short
- git branch --show-current
- git log --oneline -10

输出：
extra_ws/debug_runs/fix_until_stable/00_git_status_before.md

如果存在上一轮未提交改动：
- 分类记录。
- 属于 debug 工具和报告的，可以 commit：
  git commit -m "debug: preserve previous ORB bag diagnostic artifacts"
- 不确定的改动不要覆盖。
- 新建分支：
  debug/orb-fix-until-stable

第二阶段：读取所有已有诊断材料，不能先改参数。
读取：
extra_ws/debug_runs/latest/decision.md
extra_ws/debug_runs/latest/completion_audit.md
extra_ws/debug_runs/latest/01_sync_bag_audit.md
extra_ws/debug_runs/latest/02_mono_sync_image.md
extra_ws/debug_runs/latest/03_sync_offset_test.md
extra_ws/debug_runs/latest/04_tbc_semantics.md
extra_ws/debug_runs/latest/05_orbextractor_feature_test.md
extra_ws/debug_runs/latest 下所有 console.log、json、csv、md

生成：
extra_ws/debug_runs/fix_until_stable/01_existing_evidence_review.md

必须回答：
1. nFeatures=250 失败的直接证据是什么？
2. nFeatures=800 和 1200 是否只是完成初始化，还是已经稳定建图？
3. nFeatures=1200 为什么最终 RECENTLY_LOST / reset？
4. reset 前 5 秒是否有 inliers、tracked map points、keyframes、image_to_last_imu_ms、track_ms、队列长度的变化？
5. 现有日志缺哪些字段？
6. 之前的“结论 8”是否足以解释实际运行“很卡、一直 reset、几乎没有地图定位”？如果不足，列出缺口。

第三阶段：先扩展运行期日志，不先调参。
检查并修改 ORB_SLAM3_ROS2/src/imu_mono_realsense.cpp。

必须新增或确认已有以下日志：

1. [orb_queue]
每 1 秒输出：
- img_buf_size
- imu_buf_size
- dropped_img_count
- dropped_imu_count
- oldest_img_age_ms
- newest_img_age_ms
- processed_image_age_ms
- input_image_fps_est
- input_imu_fps_est
- orb_processed_fps_est

2. [orb_timing]
每帧输出或节流输出：
- frame_id
- image_stamp
- receive_steady_ns
- track_begin_steady_ns
- track_end_steady_ns
- cv_bridge_ms
- wait_for_imu_ms
- track_ms
- video_write_ms
- total_frame_ms
- image_age_at_track_begin_ms
- image_age_at_track_end_ms

3. [orb_imu_window]
每帧输出：
- frame_id
- image_time_sec
- track_time_sec
- imu_count
- first_imu_time_sec
- last_imu_time_sec
- imu_span_ms
- image_to_first_imu_ms
- image_to_last_imu_ms

4. [orb_state_transition]
tracking state、imu_initialized、reset_count、map_id 变化时输出：
- old_state
- new_state
- old_imu_initialized
- new_imu_initialized
- old_reset_count
- new_reset_count
- map_id
- frame_id
- last_reset_reason

5. [orb_pose_gate]
每次 timer_callback 试图发布 pose 时输出：
- tracking_state
- imu_initialized
- reset_count
- has_pose
- publish_pose
- reason

6. [orb_visual_quality]
每帧输出：
- num_features
- num_tracked_mappoints
- num_inliers
- num_keyframes
- num_matches
- tracking_state

新增参数：
- enable_video_recording，默认 false
- publish_pose_only_when_tracking_ok，默认 true
- max_image_queue_size，默认 2
- max_imu_queue_size，默认 500
- drop_stale_images，默认 true
- max_image_age_ms，默认 200
- debug_runtime_metrics，默认 true

要求：
- 先只加日志和安全参数。
- enable_video_recording 默认 false。
- 不允许此阶段修改 ORB_SLAM3 内核行为。
- 不允许此阶段调 ORBextractor 参数。

提交：
git add ORB_SLAM3_ROS2/src/imu_mono_realsense.cpp
git commit -m "debug: add ORB runtime queue timing IMU window and pose logs"

第四阶段：修复 wrapper 中明显会造成假象或 backlog 的问题。
检查 ORB_SLAM3_ROS2/src/imu_mono_realsense.cpp。

必须修复：

A. pose 发布保护：
如果 publish_pose_only_when_tracking_ok=true：
- 只有 tracking state 为 OK 或等价有效状态，且 has_pose=true，才发布 odom/tf/pose。
- NOT_INITIALIZED、RECENTLY_LOST、LOST、SYSTEM_NOT_READY、NO_IMAGES_YET 不发布新的 odom/tf。
- 不伪造零位姿。
- 不继续发布旧 Tcw_ 作为当前定位。
- 用 [orb_pose_gate] 记录拒绝发布原因。

提交：
git add ORB_SLAM3_ROS2/src/imu_mono_realsense.cpp
git commit -m "fix: prevent publishing stale pose when ORB tracking is invalid"

B. bounded queue：
image_callback：
- max_image_queue_size 默认 2。
- 超限时丢弃最旧图像。
- 记录 dropped_img_count。
- 目标是避免 TrackMonocular 慢于输入帧率后处理越来越旧的图像。

imu_callback：
- max_imu_queue_size 默认 500。
- 超限时丢弃最旧 IMU。
- 记录 dropped_imu_count。

提交：
git add ORB_SLAM3_ROS2/src/imu_mono_realsense.cpp
git commit -m "fix: bound ORB image and IMU queues to avoid stale-frame backlog"

C. 视频写盘默认关闭：
- 确认 video_writer_.write 只在 enable_video_recording=true 时执行。
- 默认 false。
- 输出 video_write_ms。

提交：
git add ORB_SLAM3_ROS2/src/imu_mono_realsense.cpp
git commit -m "fix: disable debug video recording by default during SLAM tracking"

第五阶段：建立可重复回放验证命令。
必须生成或修复：
ORB_SLAM3_ROS2/launch/h30_bag_replay.launch.py
tools/run_stability_replay.py
tools/parse_runtime_orb_log.py

要求：
1. h30_bag_replay.launch.py 只启动 ORB wrapper 和可选 ros2 bag play。
2. 不启动真实 camera/IMU/sync。
3. 支持参数：
   - bag_path
   - sensor_type
   - image_topic
   - imu_topic
   - settings_file
   - cam_imu_time_offset
   - orb_time_offset_mode
   - debug_enable
   - debug_runtime_metrics
   - enable_video_recording
   - publish_pose_only_when_tracking_ok
   - max_image_queue_size
   - max_imu_queue_size
   - drop_stale_images
   - max_image_age_ms
   - use_rviz
   - use_pangolin
   - rate
   - duration
   - qos_profile_overrides_path

4. 如果 rosbag2 回放存在 QoS 不匹配，必须生成 bag_qos_override.yaml，并使用 --qos-profile-overrides-path。
5. QoS override 的 topic 名必须精确匹配 bag 里的 topic 名：
   /sync/image_raw
   /sync/imu
   /sync/imu_batch

提交：
git add ORB_SLAM3_ROS2/launch tools
git commit -m "test: add repeatable offline ORB stability replay harness"

第六阶段：运行 baseline 修复验证。
使用上一轮表现较好的配置作为起点，但不能默认认定 1200 最优。

先运行：
- sync image + sync imu
- cam_imu_time_offset=0.0
- orb_time_offset_mode=zero_for_sync
- nFeatures=1200 临时 yaml
- enable_video_recording=false
- publish_pose_only_when_tracking_ok=true
- max_image_queue_size=2
- max_imu_queue_size=500
- drop_stale_images=true
- max_image_age_ms=200
- use_pangolin=false
- use_rviz=false

连续运行 3 次同一个 bag。

输出：
extra_ws/debug_runs/fix_until_stable/02_replay_baseline_after_wrapper_fixes.md
extra_ws/debug_runs/fix_until_stable/02_replay_baseline_after_wrapper_fixes.csv
extra_ws/debug_runs/fix_until_stable/02_replay_baseline_after_wrapper_fixes.json

必须判断：
1. 是否还卡？
2. track_ms p50/p95/max 是多少？
3. processed_image_age_ms 是否持续增长？
4. img_buf_size 是否持续增长？
5. dropped_img_count 是否增长？如果增长，是否是受控丢帧而不是无限积压？
6. reset_count 是否仍增长？
7. RECENTLY_LOST 前 5 秒发生了什么？
8. pose gate 是否阻止了 LOST 状态下的假定位输出？
9. 如果仍失败，直接原因是：
   - 性能/backlog
   - low inliers
   - map points 不稳定
   - keyframe 插入异常
   - local mapping 阻塞
   - IMU window 异常
   - QoS/回放异常
   - Tbc/time/IMU 语义错误
   - 图像质量差

第七阶段：如果 wrapper 修复后仍不稳定，进入 ORB_SLAM3 内部埋点。
只增加日志，不先改算法。

检查并必要时修改：
ORB_SLAM3/src/Tracking.cc
ORB_SLAM3/src/LocalMapping.cc
ORB_SLAM3/src/System.cc
ORB_SLAM3/include/System.h

必须增加日志事件：

[orb3_track_reason]
- frame_id
- state
- motion_model_success
- reference_keyframe_success
- relocalization_success
- track_local_map_success
- mnMatchesInliers
- mnMatchesMap
- num_tracked_mappoints
- num_close_points
- reason_if_failed

[orb3_reset_reason]
- caller
- state
- imu_initialized
- time_since_init
- mnFramesToResetIMU
- mbBadImu
- mbResetActiveMap
- reason

[orb3_keyframe_decision]
- frame_id
- need_new_keyframe
- reason
- local_mapping_busy
- tracking_state
- inliers
- ref_matches
- time_since_last_keyframe

[orb3_local_mapping]
- keyframes_in_queue
- recent_added_map_points
- local_ba_ms
- imu_ba_ms
- accepted_keyframe
- culled_keyframes
- active_map_reset_received

[orb3_imu_init]
- init_start
- init_success
- init_fail_reason
- num_keyframes
- time_span
- motion_score if available
- gravity/bias estimates if available

提交：
git add ORB_SLAM3
git commit -m "debug: add ORB-SLAM3 tracking mapping reset reason diagnostics"

第八阶段：根据证据做最小修复，不允许大矩阵。
按证据分支处理：

分支 A：如果 track_ms 太高，processed_image_age_ms 增长，说明性能/backlog 是主因。
允许修复：
1. 降低输入图像处理速率，但保持 IMU 连续：
   - 增加 target_tracking_fps 参数，例如 15、20、30。
   - 按 header stamp 或 steady time 丢弃过密图像。
   - 丢帧必须发生在 wrapper 层，不能让 queue 积压。
2. 降低 nFeatures 到能稳定实时的最小值：
   - 800
   - 1000
   - 1200
   只允许 3 个值。
3. 关闭所有非必要 debug 图像显示、视频写盘、RViz、Pangolin。
4. 编译并连续 3 次 replay 验证。

分支 B：如果 track_ms 不高，但 inliers / map points 在 reset 前下降。
允许修复：
1. 只测试有限视觉参数：
   - nFeatures: 800, 1000, 1200
   - iniThFAST/minThFAST: 固定先用 15/5
   - Camera.RGB: 只做 0/1 一次对照
2. 检查图像 encoding、是否灰度转换错误、是否压缩或颜色通道错误。
3. 输出每组 median features、inliers、tracked map points、OK ratio。
4. 选稳定性最好的，不选单帧指标最高的。

分支 C：如果 keyframe 插入异常或 LocalMapping busy。
允许修复：
1. 记录 local mapping queue。
2. 检查是否 tracking 线程被 LocalMapping 或 viewer 阻塞。
3. 关闭 viewer。
4. 如果需要，调整 keyframe 策略前必须先证明 local mapping backlog 是 reset 前兆。
5. 不允许直接大改 ORB-SLAM3 关键帧策略，除非有 clear evidence。

分支 D：如果 IMU window 异常。
允许修复：
1. 检查 image_time、track_time、first_imu、last_imu。
2. 确认 /sync/image_raw + /sync/imu 是否应 offset=0。
3. 检查是否因丢图造成 IMU window 跨度异常。
4. 检查 IMU 消息是否重复、stamp 是否跳变、频率是否异常。
5. 必要时修 wrapper 的 SyncWithImu 取 IMU 窗口逻辑。
6. 修改后 replay 验证。

分支 E：如果 ORB 内部 reset reason 指向 IMU initialization / bad IMU。
允许修复：
1. 再次验证 IMU 单位 rad/s 和 m/s²。
2. 检查 IMU noise 参数是否与实际量级明显不匹配。
3. 只允许三组 IMU noise scale：
   - current
   - current x2
   - current x5
4. 不允许同时改视觉参数。
5. 以 reset_count 和 OK ratio 判断，不以初始化速度判断。

分支 F：如果 Tbc/time 仍有证据异常。
允许修复：
1. 用源码确认 ORB_SLAM3 配置矩阵语义。
2. 只生成 corrected temporary yaml，不直接覆盖原始文件。
3. 验证当前矩阵、取逆矩阵、offset=0 三者。
4. 如果 corrected yaml 连续 3 次更稳定，才允许修改默认配置。

每个修复分支都必须：
- 写 hypothesis 文件
- 修改代码或临时配置
- git commit
- colcon build
- replay 3 次
- 写 result markdown/json
- 如果不改善，revert 或标记为 debug-only，不能继续堆叠

第九阶段：稳定性收敛。
当某组配置/代码连续 3 次满足稳定成功标准后，生成：

extra_ws/debug_runs/fix_until_stable/final_stability_report.md
extra_ws/debug_runs/fix_until_stable/best_config.yaml
extra_ws/debug_runs/fix_until_stable/final_patch_summary.md
extra_ws/debug_runs/fix_until_stable/final_commands.md

final_stability_report.md 必须包含：
1. 最终使用的 bag。
2. 最终 launch 命令。
3. 最终 config。
4. 三次 replay 的核心指标表：
   - imu_initialized_time
   - OK ratio
   - reset_count_after_init
   - final keyframes
   - median inliers
   - median tracked map points
   - track_ms p50/p95
   - processed_image_age_ms p95
   - img_buf max
   - dropped images
   - pose publish blocked count
5. 解释每个保留 commit 的必要性。
6. 说明哪些假设被排除：
   - offset
   - Tbc
   - IMU 单位
   - QoS
   - nFeatures
   - queue backlog
   - LocalMapping backlog
   - pose fake publishing
7. 说明仍然存在的风险。

完成条件：
只有当 final_stability_report.md 显示连续 3 次 replay 通过稳定成功标准，才允许声明 goal 完成。
如果达不到标准，不能用“已经解释原因”结束；必须继续进入下一证据分支或明确指出还缺什么日志字段，并补充日志后继续。