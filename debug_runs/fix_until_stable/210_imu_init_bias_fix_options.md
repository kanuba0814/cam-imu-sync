# IMU-Mono Gyro Bias 误估修复方案调研

> 适用范围：H30 单目鱼眼 + ROS 2 Humble + autoware 容器，固定 monocular 硬件。
>
> 前置：先读 [200_root_cause_correction_and_deprecation.md](200_root_cause_correction_and_deprecation.md)。

## 1 · 问题再陈述

### Root cause（已确认）

ORB-SLAM3 IMU-mono 初始化阶段（`LocalMapping::InitializeIMU`，
`libs/ORB_SLAM3/src/LocalMapping.cc:1233-1290`，本地与 upstream
算法层完全一致）使用弱 gyro 先验 `priorG = 1e2`
（`LocalMapping.cc:235`）。当 init 触发的窗口（默认 2-4 秒，本地已
yaml 调到 8 秒）正好覆盖剧烈旋转期，优化器把"真旋转"摊到 gyro bias
估计里，得到一个比真值偏大 30-300 倍的 bias。

VIBA1（5 秒）和 VIBA2（15 秒）会逐步收敛 bias，但这中间 5-15 秒
IMU 用错 bias 积分，pose 已经漂出去几公里，VIBA2 救不回来。

### 我们的实测对比

同一份 wrapper + 同一份 yaml，换 bag：

| Bag | 初次 init `bias_gx` | Post-init resets | 末态 pose drift |
|---|---|---|---|
| `h30_150hz_150s`（剧烈旋转） | 1.98 deg/s | 2 | **15 km** |
| `h30_150hz_slowMove`（温和） | 0.87 deg/s | **0** | **0.065 m** |

真值（IMU 静态）：~0.03 deg/s。slowMove 路径已经把生产场景跑稳；
本调研讨论的是"如果哪天没人盯运动纪律会不会爆"。

### 已落地的修复（前置工作）

`extra_ws/src/ORB_SLAM3_ROS2`：

- `c884187 refactor: align image queue + pose gate with official ROS2 wrapper`
- `15a7d49 refactor: drop removed parameters from h30_bag_replay launch`
- `275ad87 fix: update Camera.fps and IMU.Frequency to match h30_150hz_150s bag`
- `091439a fix: lengthen IMU init window to reduce gyro bias misestimation`

`extra_ws`：

- `a6c322b docs: deprecate fix_until_stable iteration; record real root cause`

### 本调研要回答的问题

> 除了 slowMove 运动纪律，还有什么可投资的额外加固？

下面 7 个候选，按"是否单目可用 → 是否有开源代码 → 集成成本"三层筛。

---

## 2 · 七个候选方案逐一分析

### 方案 1 — Stereo-NEC（ICRA 2024）

- **来源**：<https://github.com/ApdowJN/Stereo-NEC> ｜ <https://arxiv.org/abs/2403.07225>
- **支持单目**：❌ **stereo only**。源码 examples 全是 `stereo_inertial_*.cc`，YAML config 也只有 stereo pinhole/fisheye。Tracking.cc 路径只在 `StereoInitialization()` 调用 NEC，monocular 路径未覆盖。
- **算法核心**：用 normal epipolar constraint（双目同一时刻的 normal vector）通过最小化一个 3×3 对称矩阵的特征值，**单独**估出 gyro bias，再做联合优化。
- **开源 + license**：GPLv3，单 commit snapshot（2024-05-09），README 明说"production version 不发布"——本质是研究 demo。
- **集成成本**：理论无穷大（双目算法用不了单目硬件）；即使硬上也得加 ROS 2 wrapper（仓内无 ROS 2）+ 自适配单目。
- **维护**：Wang Weihan 单人维护，1 个 commit，无 GitHub Issue 互动。
- **结论**：❌ **不适用**。

### 方案 2 — ETA-INIT（arXiv 2405.15082, 2024）

- **来源**：<https://arxiv.org/abs/2405.15082>
- **支持单目**：❌ **stereo only**。摘要明确"target stereo VI-SLAM"，experiments 只跑 EuRoC stereo 11 序列。
- **算法核心**：把 ORB-SLAM3 的 6-DoF BA 拆成"IMU 修旋转 → 3-DoF translation BA → 联合 refine"三段，rotation 用 IMU 积分（去掉 bias 后）固定，translation 单独优化。
- **开源 + license**：❌ **paper-only**，无 github。USC + Columbia + NYU + NTU + Harbin IT 学术联盟。
- **集成成本**：需要 fork ORB-SLAM3 + 改 `Optimizer::InertialOptimization` + 改 G2oTypes，无 reference impl 时全部从论文翻。
- **维护**：仅论文版本（v1 2024-05、v3 2024-08）。
- **结论**：❌ **不适用**（双目专用 + 无代码）。

### 方案 3 — DOGE（arXiv 2412.08135, 2024）

- **来源**：<https://arxiv.org/abs/2412.08135>
- **支持单目**：✓ **算法可适配**。DOGE 估的是外参方向 + gyro bias（rotation-only constraint），与尺度无关，理论上可作为单目预处理。
- **算法核心**：在 init 之前，用 normal epipolar constraint 联合估出 `T_cam_imu` 的旋转部分 + gyro bias，IRLS 加权 + chi-square 失败检测。输出：refined gyro bias + extrinsic rotation。
- **开源 + license**：❌ **paper-only**。CASIA + TCL RayNeo（中科院 + 工业），NSFC funded。
- **集成成本**：理论上可以做成"ORB 之前的 wrapper preprocess"，不必 fork ORB；但要用 Ceres 从论文公式手实现 ~100ms 的优化器，**realistic 1-2 周** 工作量，不在 3-5 天预算内。
- **维护**：2024-12 提交，无 follow-up 代码。
- **结论**：⚠️ **理论可行但超出预算**（手实现风险高）。

### 方案 4 — Structureless VIBA（arXiv 2502.16598, ICRA 2025）

- **来源**：<https://arxiv.org/abs/2502.16598>
- **支持单目**：✓ **显式 monocular-inertial**。University of Luxembourg。
- **算法核心**：跳过 3D structure 重建，用 structureless VIBA 直接联合估 rotation/translation/velocity/bias/gravity。降低状态向量维度，初始化更快更准。
- **开源 + license**：❌ **暂未发布**（论文 2025-02 发，距今 < 3 个月，ICRA 2025 待会议后看作者是否开源）。
- **集成成本**：n/a（无代码）。
- **维护**：太新。
- **结论**：⚠️ **保持观察**——是单目专用且最新，但要等 reference code。

### 方案 5 — priorG / priorA 常量调参

- **来源**：本地 `libs/ORB_SLAM3/src/LocalMapping.cc:235`，upstream 同。
- **支持单目**：✓
- **算法核心**：把 `InitializeIMU(1e2, 1e10, true)` 的 priorG 从 `1e2` 提到 `1e4` 或 `1e5`，强迫 ORB 优化器更相信"bias 应该接近 0"，减少把运动当 bias 的概率。
- **开源 + license**：本地源码可改。GPLv3。
- **集成成本**：**1 行 C++ 改动**。或更稳妥地暴露成 yaml `LocalMapping.PriorG`、`LocalMapping.PriorA`。
- **维护风险**：**没有任何社区 fork 文档化过这种 tuning**。理论上若 IMU 真 bias 不为 0，强先验会把估计往 0 拉，反而错。需要配合方案 6（先测出真 bias，再把 prior 中心放在那）才稳。
- **结论**：⚠️ **可作为方案 6 的辅助选项**，单独使用风险大于收益。

### 方案 6 — Wrapper warm-up bias 减除

- **来源**：实操方案，无 paper 也无社区 fork（已查 thien94 / Mechazo11 / gjcliff / jnskkmhr 等主流 wrapper，**均未实现**）。
- **支持单目**：✓
- **算法核心**：wrapper 启动后开一个"warm-up 期"（默认 3-5 秒），在此期间：
  1. 收集 IMU samples 的 gyro/accel 流
  2. 用 gyro 模长判定相机是否真静止（`|gyro| < 5 deg/s` 持续 N samples）
  3. 若静止，平均 gyro 得到经验静态 bias `b̂_g`
  4. 静止判定通过后，wrapper **从所有后续转发给 ORB 的 IMU 消息中减去 `b̂_g`**
  5. 若静止判定失败（启动时就在动），跳过减除、只在日志里 warn，行为退化到当前
- **开源 + license**：n/a（wrapper 自己写）。
- **集成成本**：**纯 wrapper 改动，零 ORB 修改**。改 `imu_mono_realsense.cpp::imu_callback` 和 `init`。预算 2-3 天（含端到端验证）。
- **维护风险**：低。
  - 若 warm-up 误判（启动时在动），退化为"不减除"，跟现状等价
  - 若 IMU 漂移（长时间运行后真 bias 变了），warm-up 阶段估的 bias 会过期；但 ORB 自己有 VIBA1/2 收敛 bias，把残差吸走
  - bias 减除后 ORB 内部估计的 bias 会接近 0（因为已经被减掉了），这与 ORB 的 prior=0 假设更一致，反而更稳
- **预期改善**：在剧烈运动 bag 上，把 init 时的 bias 误差从 60-300x 真值降到 ~1-2x；pose drift 可控。slowMove bag 上无变化。
- **结论**：✅ **推荐**。

### 方案 7 — slowMove 运动纪律（现状）

- **来源**：本轮验证。
- **支持单目**：✓
- **算法核心**：录数据 / 启动相机时，强制前 10 秒做 gyro < 15 deg/s 的温和运动（含 translation + roll + pitch）。
- **开源 + license**：n/a。
- **集成成本**：零代码，靠 SOP 文档 + 操作员训练。
- **维护风险**：**如果用户没遵守 SOP，单次启动就废**。无技术防线。
- **预期改善**：实测 0.065m drift、0 reset、62 KF（已验证）。
- **结论**：✅ **基线保持**。

---

## 3 · 决策表

| # | 方案 | 单目支持 | 开源代码 | 集成成本 | 预期改善 | 风险 |
|---|---|---|---|---|---|---|
| 1 | Stereo-NEC | ❌ | ✓ | n/a | n/a | 双目专用，淘汰 |
| 2 | ETA-INIT | ❌ | ❌ | n/a | n/a | 双目+无代码，淘汰 |
| 3 | DOGE 手实现 | ✓ | ❌ | **2 周+** | 高（理论） | 超预算 + 手实现风险 |
| 4 | Structureless VIBA | ✓ | ❌（待发布） | n/a | n/a | 等代码 |
| 5 | priorG 调参 | ✓ | ✓ | 1 行 | 低 | 单独使用反而错 |
| 6 | **Wrapper warm-up bias** | ✓ | n/a（自写） | **2-3 天** | 中-高 | **低** |
| 7 | **slowMove 纪律**（现状） | ✓ | n/a | 0 | 已验证 | 操作纪律失败时无防线 |

筛选后进入二选行的只有 **方案 6 + 方案 7**。

### 三个执行选项

| 选项 | 内容 | 工作量 | 适合谁 |
|---|---|---|---|
| **保持现状**（基线） | 只用方案 7（slowMove 纪律），写 SOP | 0.5 天（写文档） | 启动场景完全可控的部署 |
| **加固 A**（推荐） | 方案 6（wrapper warm-up bias 减除），保留方案 7 兜底 | **2-3 天** | 担心运动纪律偶尔失守的部署 |
| **加固 B** | 方案 6 + 方案 5（priorG yaml 暴露），保留方案 7 | 3-5 天 | 想给后续用户更多调参空间 |

不推荐：方案 3（DOGE 手实现）— 超预算 + 风险高 + 没 reference impl。
保持观察：方案 4（Structureless VIBA）— 等 ICRA 2025 后看是否开源。

### 加固 A 的具体落地（2-3 天）

**改的文件**：

- `extra_ws/src/ORB_SLAM3_ROS2/src/imu_mono_realsense.cpp`
  - `init()`：声明 3 个新参数 `imu_warmup_sec`（默认 3.0）、`imu_warmup_max_gyro_degs`（默认 5.0）、`imu_warmup_enabled`（默认 true）
  - 类成员：`bool warmup_done_`、`Eigen::Vector3d estimated_gyro_bias_`、`std::vector<Imu> warmup_samples_`、`rclcpp::Time warmup_start_time_`
  - `imu_callback()`：在 `warmup_done_=false` 阶段把 sample 推入 warmup buffer 并判定静止；warmup 通过后转 `warmup_done_=true` + 算 `estimated_gyro_bias_`；warmup 失败（动太厉害）也设 `warmup_done_=true` 但 bias=0、log warn
  - `imu_callback()`：转发给 ORB 之前 `gyro -= estimated_gyro_bias_`
  - 启动 banner 加 warmup 状态

**验收**：

| Bag | 现状 | 加固 A 期望 |
|---|---|---|
| `h30_150hz_slowMove`（基线） | 0.065m drift, 0 reset | **不退步**：drift < 0.5m，0 post-init reset |
| `h30_150hz_150s`（剧烈） | 15km drift, 2 post-init reset | **改善**：drift < 10m（理想 < 1m），post-init reset ≤ 1 |

如果加固 A 在 slowMove bag 上退步（drift 升或 reset 增），立即回滚。

**Fallback**：参数 `imu_warmup_enabled:=false` 一刀关；或 git revert。

---

## 4 · 推荐 + 不推荐

| | 选项 |
|---|---|
| **推荐** | 保持方案 7（slowMove）作为生产路径；如果运动纪律有担忧，预算 2-3 天上加固 A（方案 6 wrapper warm-up） |
| **不推荐** | 方案 1/2（双目专用）；方案 3（DOGE 手实现，预算外）；方案 5 单用（priorG 单独调） |
| **观察** | 方案 4（Structureless VIBA）—— ICRA 2025 之后跟踪作者是否开源，开源后再评估 |

### 不投资也合理的判断依据

- slowMove bag 已实测 0.065m drift、0 post-init reset、62 KF——这已经是**生产可用**的 SLAM。
- 加固 A 只解决"用户不按 SOP 启动相机时是否会全废"——如果业务保证启动顺序（机械平台 boot-up routine 可定制），方案 7 完全够用。
- 加固 A 没有把 rough motion bag 救活的把握（那个 bag 整段都剧烈旋转，warm-up 阶段也估不到准 bias）。

---

## 5 · 引用

### 学术
- [Stereo-NEC (ICRA 2024) — Enhancing Stereo VI-SLAM Initialization with Normal Epipolar Constraints](https://github.com/ApdowJN/Stereo-NEC)
- [Stereo-NEC paper](https://arxiv.org/abs/2403.07225)
- [ETA-INIT — Enhancing Translation Accuracy for Stereo VI SLAM Initialization](https://arxiv.org/abs/2405.15082)
- [DOGE — Extrinsic Orientation and Gyroscope Bias Estimation for VIO Initialization](https://arxiv.org/abs/2412.08135)
- [Structureless VIBA (ICRA 2025) — Improving Monocular VI Initialization](https://arxiv.org/abs/2502.16598)

### ORB-SLAM3 GitHub Issues（社区共识）
- [#69 Looping "IMU not initialized"](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/69)
- [#356 Mono-Inertial: Fail to track local map after IMU init](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/356)
- [#435 IMU initialization at high velocity](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/435)
- [#736 A summary of mono-inertial initialization issues, and suggestions for others](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/736)
- [#910 IMU problem with Mono-Inertial mode using Gazebo + RViz2](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/910)
- [#933 Problem Initializing IMU for OrbSlam3 on EuRoC dataset](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/933)
- [#968 Methodical issue in inertial-only optimization (IMU initialization)?](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/968)

### 本仓 commit 索引

`extra_ws/src/ORB_SLAM3_ROS2`：

- `c884187` — wrapper 队列对齐官方
- `15a7d49` — launch 清理
- `275ad87` — yaml 频率匹配新 bag
- `091439a` — IMU init 窗口加长

`extra_ws`：

- `a6c322b` — 200_*.md 废弃 codex 旧迭代

### 反向引用

- 上下文：[200_root_cause_correction_and_deprecation.md](200_root_cause_correction_and_deprecation.md)
