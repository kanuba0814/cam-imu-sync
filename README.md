# cam-imu-sync · 单目-惯性 SLAM 的相机 / IMU 确定性时间同步

实验室项目（2026.02 – 2026.05）。硬件是 USB 相机（640×480 @ 30 fps）加 Yesense H30 IMU（200 Hz），软件栈为 ROS 2 Humble、usb_cam、yesense_ros2 和 ORB-SLAM3，用 Kalibr 做 IMU-相机标定。

## 问题与结果

用 Kalibr 标定时发现：同一次启动内 timeshift 很稳定，**但每次重启后都会随机跳变，范围接近 1 秒**。空间外参可信，时间标定却完全不能用。

根因是两个驱动各自取 ROS 时间，两个时间域的启动锚点都是随机的。最终方案（Phase 1A）：

- IMU 驱动在帧解码时刻记录 `steady_clock`，新增 `/imu/raw_hw` 消息（驱动修改见 `patches/yesense_ros2/`）；
- 同步节点用**同一个** `steady_ns → ROS 时间`映射函数重写相机和 IMU 的 header，offset 在启动时固定；
- 加入启动状态机（WAIT_IMU_READY → WAIT_CAM_STABLE → WAIT_FIRST_SYNC → READY），并在同一时钟域内插值 IMU。

| 指标 | 无同步 | sync v1 | steady + 驱动改造 | **Phase 1A** |
|---|:---:|:---:|:---:|:---:|
| bag 数 / 启动次数 | 11 / ~6 | 4 / 4 | 18 / 7 | **10 / 5** |
| 跨启动 timeshift 极差 | ~972 ms | ~191 ms | 924.6 ms | **2.48 ms** |
| timeshift 标准差 | — | — | 251 ms | **0.74 ms** |

完整的迭代过程和全部标定数据见 [`workspace/report/imu_cam_deterministic_sync_report.md`](workspace/report/imu_cam_deterministic_sync_report.md)。

另外修复了 ORB-SLAM3 ROS 2 封装在 bag 回放中频繁 reset 的问题：延长 IMU 初始化窗口、预热期扣除陀螺零偏、加入图像队列和位姿质量门控。这部分在同账号下的 `ORB_SLAM3_ROS2` fork 仓库中，每一项都按“假设 → 修改 → 回放验证”单独提交，过程记录在 `debug_runs/fix_until_stable/`。

## 目录

```text
src/cam_imu_sync/          同步节点：sync_manager（统一时钟映射与状态机）、fixed_rate_resampler、diagnostics
src/imu_tf_broadcaster/    IMU 姿态 TF 广播
patches/yesense_ros2/      对厂商 IMU 驱动的 6 个补丁（驱动本身不在本仓库中分发）
tools/、scripts/           bag 审计与稳态实验分析脚本
debug_runs/                ORB-SLAM3 稳定性排查的逐步记录
workspace/report/          确定性同步报告与简报
workspace/docs/            同步节点设计文档与第二轮稳态方案
workspace/kalibr/          Kalibr camchain / imucam 标定结果与脚本
workspace/goal/            给 Agent 的 ORB-SLAM3 排查目标说明
```

## 运行测试

```bash
cd src/cam_imu_sync
python3 -m pytest test/test_sync_manager.py test/test_fixed_rate_resampler.py   # 48 passed
```

完整构建需要 ROS 2 Humble：`colcon build --packages-select cam_imu_sync imu_tf_broadcaster`。

## 与 AI Agent 的协作方式

- 工作区规则写在 [`workspace/AGENTS.md`](workspace/AGENTS.md) 和 [`workspace/CLAUDE.md`](workspace/CLAUDE.md)：ROS 包只能在指定容器里构建和测试，lint 失败视为阻塞，每个提交只做一件事，并且必须附上实际运行过的验证命令。
- 排查 ORB-SLAM3 时，我先把目标和验收条件写成 [`workspace/goal/orbDebugGoalV2.md`](workspace/goal/orbDebugGoalV2.md)，再让 Agent 按“假设 → 修改 → 回放验证”循环推进。某条假设被证伪后，结论也会写回文档（例如 `docs: deprecate fix_until_stable iteration; record real root cause`）。
- `claude_modify` 分支保留了 Agent 生成的最初工作区基线，便于和后续人工修正对照。

## 分支

- `main`：Phase 1A 模块化同步实现、报告和标定结果
- `feat/cam-imu-sync-resampled-imu`：固定频率重采样 IMU 实验
- `wip/single-node-sync`：发布时工作区中的简化单文件版本（排查 ORB-SLAM3 时使用），未合入 main
- `claude_modify`：Agent 生成的初始基线
