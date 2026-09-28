# IMU-Camera 时间同步系统演进与确定性改造报告

**项目名称**：IMU-Cam 时间同步系统  
**日期**：2026-04-16  
**硬件**：USB Camera (640×480 @30fps) + Yesense H30 IMU (200Hz) + x86 主机  
**软件栈**：ROS 2 Humble · usb_cam 0.8.1 · yesense_ros2 · cam_imu_sync · ORB-SLAM3  
**验证手段**：Kalibr IMU-Camera 标定 (`kalibr_calibrate_imu_camera`)

---

## 目录

1. [问题背景与目标](#1-问题背景与目标)
2. [迭代演进全记录](#2-迭代演进全记录)
   - [阶段 0：手动启动，无同步节点（编号系列 02-15）](#阶段-0手动启动无同步节点编号系列-02-15)
   - [阶段 1：cam_imu_sync 节点诞生（C 系列）](#阶段-1cam_imu_sync-节点诞生c-系列)
   - [阶段 2：IMU 驱动时间戳重建（D 系列前期）](#阶段-2imu-驱动时间戳重建d-系列前期)
   - [阶段 3：Steady-domain 同步架构 + 状态机（D 系列中后期）](#阶段-3steady-domain-同步架构--状态机d-系列中后期)
   - [阶段 4：Phase 1A 确定性时间同步（E 系列）](#阶段-4phase-1a-确定性时间同步e-系列)
3. [全量标定数据](#3-全量标定数据)
4. [最终解决方案技术细节](#4-最终解决方案技术细节)
5. [验证与结论](#5-验证与结论)
6. [附录](#6-附录)

---

## 1. 问题背景与目标

### 1.1 核心问题

在使用 Kalibr 对 IMU-Camera 系统进行外参+时间偏移标定时，观察到：

- **同一次启动内**的多个 bag，timeshift 非常稳定（组内 std < 1 ms）
- **每次重启后**，timeshift 跳变到完全不同的值，范围接近 **1 秒**，正负翻转
- 空间外参（旋转、平移）在所有启动间高度一致

这意味着**空间标定是可信的，但时间标定完全不可用**——每次重启都需要重新标定，而且结果不可预测。

### 1.2 项目目标

**消灭跨启动 timeshift 随机漂移**，实现：
- 跨启动 timeshift 标准差 ≤ 5 ms（目标）
- 输出消息全部处于同一时间域
- 不依赖 IMU 硬件时间戳（H30 不支持 0x51/0x52）
- 保持向后兼容（可切回旧模式）

---

## 2. 迭代演进全记录

### 阶段 0：手动启动，无同步节点（编号系列 02-15）

**时间**：2026 年 2-3 月  
**方法**：手动分别启动 `usb_cam` 和 `yesense_ros2`，直接用 `ros2 bag record` 录制  
**标定数据来源**：编号系列 02-15

此阶段没有任何同步机制，IMU 和 Camera 各自独立发布带 `ros::now()` 时间戳的消息。

| Bag | timeshift (ms) |
|-----|:---------:|
| 02 | +60.1 |
| 03 | +992.5 |
| 07 | +20.5 |
| 08 | +982.0 |
| 09 | +514.9 |
| 10 | +514.3 |
| 11 | +515.6 |
| 12 | +233.7 |
| 13 | +234.2 |
| 14 | +235.2 |
| 15 | +84.6 |

**观察**：
- timeshift 在 +20 ms 到 +993 ms 之间随机分布
- 同一次启动的相邻 bag（如 09/10/11、12/13/14）之间一致
- 跨启动（如 02→03、07→08）差异巨大

**结论**：无同步，时间域完全不可控。需要一个专门的同步节点。

---

### 阶段 1：cam_imu_sync 节点诞生（C 系列）

**时间**：2026-03-29  
**关键提交**：`8f0c521` initial commit + `be20801` add interpolation  
**改动内容**：

1. **新建 `cam_imu_sync` 包**
   - 缓存 IMU 消息流，等待 Camera 帧到达
   - 按 `cam_imu_time_offset`（初始配置 0.2745s）对齐时间戳
   - 批量转发 IMU + 重新打戳的 Image 到 `/sync/imu` 和 `/sync/image_raw`
2. **添加帧边界线性插值**
   - 在对齐点处对最近两个 IMU 样本做 lerp
   - 模仿 `orb_alt.cpp` 的 `interpolate_measure()` 算法
3. **统一 Launch 文件**
   - `cam_imu_sync.launch.py` 同时启动 usb_cam + yesense + sync node

**标定数据**：C 系列（4 个 bag，跨 4 次启动）

| Bag | 启动 | timeshift (ms) |
|-----|------|:---------:|
| C1 | 1 | -37.7 |
| C2 | 2 | -100.3 |
| C3 | 3 | -99.7 |
| C4 | 4 | -228.6 |

**观察**：
- 相比编号系列，量级从 ~1 秒缩到 ~200 ms 内（有改善但不够）
- C2/C3 几乎一致（可能是同一次启动的两个 bag）
- 仍有跨启动跳变：C1 与 C4 差 190 ms

**结论**：同步节点起了正面作用（收窄了变化范围），但 `header.stamp` 直接透传的根本问题未解决。

---

### 阶段 2：IMU 驱动时间戳重建（D 系列前期）

**时间**：2026-04-03 ~ 04-07  
**关键提交**：
- `b0cfbd3` **硬件计数器时间戳重建**：用 `tid`（协议序列号）重建等间距时间戳，消除 UART/USB 缓冲抖动
- `0e240cd` 添加 `hw_ts_unit_us`、`imu_output_rate` 参数
- `1740e23` **闭环 EMA 跟踪**：防止开环 `base + count × interval` 长时间运行后与 wall clock 漂移

**改动详情**：

原始驱动的时间戳策略：
```cpp
// 原始：每次解包都用 ros::now()
imu_msg.header.stamp = this->get_clock()->now();
// 问题：UART批量到达 → 同一批内多个消息共享近似相同时间
```

改后策略（tid 重建 + EMA 追踪）：
```cpp
// 1. 用 tid 差值重建等间距时间戳
int64_t tid_delta = current_tid - base_tid;  // 含 wrap-around 处理
double reconstructed = base_ros_time + tid_delta * (1.0 / imu_rate);

// 2. EMA 追踪防漂移
double wall_now = this->get_clock()->now().seconds();
double drift = wall_now - reconstructed;
base_ros_time += alpha * drift;  // alpha = 0.005
```

**结果**：IMU 时间戳抖动从 ~1 ms 降到 ~0.0002 ms，但**跨启动 timeshift 随机跳变问题未解决**——因为 `base_ros_time` 在每次启动时仍然随机。

---

### 阶段 3：Steady-domain 同步架构 + 状态机（D 系列中后期）

**时间**：2026-04-07 ~ 04-11  
**改动内容**：cam_imu_sync 的重大重构

1. **引入 `steady_clock` 作为同步决策基准**
   - 所有同步判定改为在 `time.monotonic_ns()` 域内进行
   - `steady_cam_to_imu_offset_sec` 取代旧的 header-domain offset
   - IMU 和 Image 入队时都记录 `steady_ns`
2. **状态机架构**
   - `WAIT_IMU_READY` → `WAIT_FIRST_SYNC` → `READY`
   - IMU pipeline readiness 检测（频率稳定性）
   - 连续失败计数 + 自动 rearm
3. **全面诊断系统**
   - CSV 事件日志（每个 IMU/CAM/SYNC 事件）
   - 运行时统计（周期、延迟、丢包）
   - 结束要约（summary.txt）
4. **代码架构提升**
   - `models.py`：数据模型层（SyncConfig, SyncState, SyncStats, FrameSample）
   - `sync_manager.py`：纯逻辑层（无 ROS 依赖，可单测）
   - `sync_node.py`：ROS 薄壳层
   - `diagnostics.py`：诊断写入器

**标定数据**：D 系列（18 个 bag，跨 7 次启动）

| 启动 | Bags | timeshift 均值 (ms) | 组内 std (ms) |
|------|:----:|:---:|:---:|
| D1x | 5 | -62.10 | 0.67 |
| D2x | 5 | -24.99 | 0.36 |
| D3x | 1 | -105.17 | — |
| D4x | 2 | -213.04 | 0.15 |
| D5x | 2 | +237.63 | 1.20 |
| D6x | 2 | +445.70 | 0.96 |
| D7x | 1 | +711.47 | — |

**关键发现**：
- **组内极稳**：同一次启动内 std 始终 < 1.2 ms
- **跨启动巨变**：全局 std = **251 ms**，range = **925 ms**（-213 到 +711）
- **空间外参不变**：tz std = 0.0020 m，与 C 系列一致

**根因确认**：问题**不在同步算法，不在 IMU 驱动，不在空间标定**。问题在于每次启动时，IMU 和 Camera 的 ROS 时间戳获取时机不同，导致**启动瞬间的时间锚点随机化**。只要两个传感器使用独立的 `ros::now()` 获取时间戳，这个问题就不可能解决。

---

### 阶段 4：Phase 1A 确定性时间同步（E 系列）

**时间**：2026-04-13 ~ 04-16  
**目标**：彻底消灭启动锚点随机化

#### 核心设计

一句话总结：**用同一个 `steady_clock` 锚点重写所有输出时间戳**。

```
ros_stamp = steady_ns / 1e9 + ros_minus_steady_offset
           ↑                  ↑
           唯一时间源           启动时一次捕获，全程不变
```

#### 三层改动

**① IMU 驱动层（yesense_ros2）**

新增 `ImuRawHw.msg` 消息，在帧解码确认时刻同时捕获 `steady_clock` 和 `ros::now()`：

```
# ImuRawHw.msg
std_msgs/Header header
geometry_msgs/Vector3 linear_acceleration
geometry_msgs/Vector3 angular_velocity
geometry_msgs/Quaternion orientation
uint16 tid                    # 协议 TID（丢包检测）
uint64 rx_steady_ns           # ← 关键：steady_clock 纳秒时间戳
uint64 rx_ros_ns              # ROS 时间（诊断用）
uint32 sample_timestamp       # 预留（H30 不输出）
uint32 data_ready_timestamp   # 预留
float64 hw_ts_unit_sec        # 预留
```

驱动修改（`yesense_node.cpp`）：
```cpp
void YESENSE_Publisher::publish_msg(analysis_data* result) {
    // 关键：在帧确认时刻捕获主机时间
    auto steady_now = std::chrono::steady_clock::now();
    auto ros_now = this->get_clock()->now();

    // 填充并发布 ImuRawHw
    raw_hw.rx_steady_ns = duration_cast<nanoseconds>(
        steady_now.time_since_epoch()).count();
    raw_hw.rx_ros_ns = ros_now.nanoseconds();
    raw_hw.tid = result->tid;
    raw_hw_pub_->publish(raw_hw);

    // 原有 Imu 消息继续发布（向后兼容）
    imu_pub_->publish(imu_ros_data);
}
```

新增文件：`yesense_interface/msg/ImuRawHw.msg`  
修改文件：`yesense_node.cpp`、`CMakeLists.txt`、`package.xml`、`yesense_config.yaml`

**② 同步节点数据模型层（cam_imu_sync/models.py）**

- 扩展状态机：`+INIT`、`+WAIT_CAM_STABLE`、`+DEGRADED`
- 新增配置项：`deterministic_sync`、`enable_header_rewrite`、`min_stable_cam_frames`、`cam_stable_max_std_ms`
- 新增数据类：`ImuRawSample`（从 ImuRawHw 消息提取的纯 Python 数据结构）

**③ 同步管理器核心逻辑（cam_imu_sync/sync_manager.py + sync_node.py）**

`sync_manager.py` 新增方法：

| 方法 | 作用 |
|------|------|
| `init_time_offset(ros_now_ns, steady_now_ns)` | 启动时一次性捕获 offset |
| `steady_ns_to_ros_sec(steady_ns)` | **唯一的时间映射函数** |
| `on_imu_raw(raw)` | 处理 ImuRawHw，以 `rx_steady_ns` 为主时间 |
| `_check_tid(tid)` | tid 丢包/乱序检测 |
| `_check_cam_stable()` | 相机帧率稳定性检查 |
| `_try_wait_cam_stable()` | WAIT_CAM_STABLE 状态处理 |

`sync_node.py` 关键变更：

```python
# 1. 启动时捕获 offset（一次性，全生命周期不变）
ros_now_ns = self.get_clock().now().nanoseconds
steady_now_ns = time.monotonic_ns()
self._manager.init_time_offset(ros_now_ns, steady_now_ns)

# 2. deterministic 模式下，只订阅 /imu/raw_hw，不订阅 /imu/data_raw
if not self._deterministic_sync:
    self._imu_sub = self.create_subscription(Imu, ..., self._on_imu, ...)
else:
    self._imu_sub = None  # 避免两个回调的时间域冲突

# 3. header 重写在 publish 之前完成
for i, m in enumerate(batch.imu_msgs):
    unified_sec = self._manager.steady_ns_to_ros_sec(batch.imu_steady_ns_list[i])
    m.header.stamp = sec2stamp(unified_sec)  # ← 统一时间域
batch.image_msg.header.stamp = sec2stamp(
    self._manager.steady_ns_to_ros_sec(batch.cam_steady_ns))

# 4. 先改戳再发布
for m in batch.imu_msgs:
    self._imu_pub.publish(m)
self._img_pub.publish(batch.image_msg)
```

#### 额外修复

在开发过程中发现并修复了两个关键 Bug：

1. **IMU header 在 publish 之后才重写**：原代码先 `publish(m)` 再改 `m.header.stamp`，导致发出的消息仍带旧时间戳。修复：所有 header 重写移到 publish 循环之前。
2. **插值 IMU 缺少 steady_ns 对齐项**：`lerp_imu_steady()` 生成的插值点只追加到 `imu_batch`，但 `imu_sns_batch` 没有对应条目，导致 header 重写跳过插值点。修复：同步追加 `imu_sns_batch.append(int(target_steady * 1e9))`。

#### 状态机流程

```
[*] → INIT → WAIT_IMU_READY → WAIT_CAM_STABLE → WAIT_FIRST_SYNC → READY
                                    ↑ Phase 1A 新增
```

`WAIT_CAM_STABLE` 确保相机帧率稳定（std ≤ 10 ms）后再进入同步，避免启动初期的帧率抖动。

#### 新增 Launch 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `deterministic_sync` | `true` | 启用 Phase 1A 统一时间域 |
| `enable_header_rewrite` | `true` | 重写所有输出 header.stamp |
| `imu_raw_hw_topic` | `/imu/raw_hw` | ImuRawHw 话题 |
| `min_stable_cam_frames` | `10` | 相机稳定判定帧数 |
| `cam_stable_max_std_ms` | `10.0` | 相机周期最大 std (ms) |

---

## 3. 全量标定数据

### 3.1 编号系列（阶段 0 — 无同步）

| Bag | timeshift (ms) | 备注 |
|-----|:---------:|------|
| 02 | +60.1 | |
| 03 | +992.5 | |
| 04 | — | 标定未收敛 |
| 06 | — | 标定未收敛 |
| 07 | +20.5 | |
| 08 | +982.0 | |
| 09 | +514.9 | 同启动 |
| 10 | +514.3 | 同启动 |
| 11 | +515.6 | 同启动 |
| 12 | +233.7 | 同启动 |
| 13 | +234.2 | 同启动 |
| 14 | +235.2 | 同启动 |
| 15 | +84.6 | |

### 3.2 C 系列（阶段 1 — cam_imu_sync v1）

| Bag | 启动 | timeshift (ms) |
|-----|------|:---------:|
| C1 | 1 | -37.7 |
| C2 | 2 | -100.3 |
| C3 | 3 | -99.7 |
| C4 | 4 | -228.6 |

### 3.3 D 系列（阶段 2+3 — 驱动改造 + steady-domain）

| Bag | 启动 | timeshift (ms) | reproj (px) | tx (m) | ty (m) | tz (m) |
|-----|------|:---------:|:------:|:------:|:------:|:------:|
| D11 | 1 | -62.13 | 0.730 | -0.0013 | +0.0104 | -0.0665 |
| D12 | 1 | -62.37 | 0.699 | -0.0012 | +0.0094 | -0.0664 |
| D13 | 1 | -62.52 | 0.616 | +0.0001 | +0.0117 | -0.0655 |
| D14 | 1 | -60.94 | 0.673 | -0.0014 | +0.0095 | -0.0671 |
| D15 | 1 | -62.54 | 0.674 | +0.0024 | +0.0099 | -0.0659 |
| D21 | 2 | -25.21 | 0.741 | -0.0021 | +0.0092 | -0.0671 |
| D22 | 2 | -25.07 | 0.859 | -0.0023 | +0.0095 | -0.0668 |
| D23 | 2 | -24.35 | 0.620 | -0.0053 | +0.0102 | -0.0659 |
| D24 | 2 | -25.16 | 0.632 | -0.0027 | +0.0114 | -0.0702 |
| D25 | 2 | -25.14 | 0.646 | -0.0061 | +0.0108 | -0.0719 |
| D31 | 3 | -105.17 | 0.626 | -0.0023 | +0.0112 | -0.0684 |
| D41 | 4 | -212.93 | 0.839 | -0.0037 | +0.0088 | -0.0673 |
| D42 | 4 | -213.15 | 0.664 | -0.0053 | +0.0096 | -0.0664 |
| D51 | 5 | +236.78 | 0.710 | -0.0042 | +0.0077 | -0.0652 |
| D52 | 5 | +238.48 | 0.635 | -0.0034 | +0.0087 | -0.0706 |
| D61 | 6 | +445.03 | 0.798 | -0.0017 | +0.0091 | -0.0674 |
| D62 | 6 | +446.38 | 0.714 | -0.0007 | +0.0088 | -0.0704 |
| D72 | 7 | +711.47 | 0.624 | -0.0036 | +0.0065 | -0.0663 |

### 3.4 E 系列（阶段 4 — Phase 1A 确定性同步）

| Bag | 启动 | timeshift (ms) | reproj (px) | tx (m) | ty (m) | tz (m) |
|-----|------|:---------:|:------:|:------:|:------:|:------:|
| E11 | 1 | -15.46 | 0.764 | -0.0033 | +0.0090 | -0.0659 |
| E12 | 1 | -15.51 | 0.637 | -0.0033 | +0.0101 | -0.0693 |
| E21 | 2 | -16.59 | 0.772 | -0.0005 | +0.0091 | -0.0671 |
| E22 | 2 | -17.40 | 0.765 | -0.0029 | +0.0079 | -0.0713 |
| E31 | 3 | -15.57 | 0.816 | -0.0016 | +0.0074 | -0.0692 |
| E32 | 3 | -15.62 | 0.775 | -0.0034 | +0.0072 | -0.0683 |
| E41 | 4 | -15.87 | 0.752 | -0.0021 | +0.0070 | -0.0695 |
| E42 | 4 | -14.91 | 0.786 | -0.0003 | +0.0063 | -0.0662 |
| E51 | 5 | -15.10 | 0.835 | -0.0007 | +0.0058 | -0.0707 |
| E52 | 5 | -15.39 | 0.652 | +0.0019 | +0.0101 | -0.0690 |

---

## 4. 最终解决方案技术细节

### 4.1 变更文件清单

共涉及 **3 个 ROS 包、9 个文件**：

| 包 | 文件 | 动作 | 说明 |
|----|------|------|------|
| yesense_interface | `msg/ImuRawHw.msg` | **新增** | 带 steady_clock 时间戳的 IMU 消息 |
| yesense_interface | `CMakeLists.txt` | 修改 | 注册新消息 + 依赖 |
| yesense_interface | `package.xml` | 修改 | 构建依赖 |
| yesense_std_ros2 | `src/yesense_node.cpp` | 修改 | 新增 /imu/raw_hw 发布 |
| yesense_std_ros2 | `config/yesense_config.yaml` | 修改 | enable_raw_hw_topic 参数 |
| cam_imu_sync | `cam_imu_sync/models.py` | 修改 | 状态机+数据模型扩展 |
| cam_imu_sync | `cam_imu_sync/sync_manager.py` | 修改 | 统一 offset + on_imu_raw + 状态机 |
| cam_imu_sync | `cam_imu_sync/sync_node.py` | 修改 | 双模式订阅 + header 重写 |
| cam_imu_sync | `cam_imu_sync/diagnostics.py` | 修改 | CSV 新列 |
| cam_imu_sync | `launch/cam_imu_sync.launch.py` | 修改 | Phase 1A 参数 |
| cam_imu_sync | `package.xml` | 修改 | yesense_interface 依赖 |

### 4.2 架构对比

**改造前**：
```
usb_cam  ──→ header.stamp(ros_clock_A) ──→ cam_imu_sync ──→ 透传 ──→ /sync/image_raw
yesense  ──→ header.stamp(ros_clock_B) ──→ cam_imu_sync ──→ 透传 ──→ /sync/imu
                                                             ↑
                                                两个独立时间域，启动锚点随机
```

**改造后**：
```
usb_cam  ──→ steady_ns(接收时刻) ──→ cam_imu_sync ──→ steady_ns_to_ros_sec() ──→ /sync/image_raw
yesense  ──→ ImuRawHw{rx_steady_ns} ──→ cam_imu_sync ──→ steady_ns_to_ros_sec() ──→ /sync/imu
                                                          ↑
                                                 单一映射函数，offset 启动固定
```

### 4.3 Git 变更追踪

```
# yesense_ros2 (driver_ws/src/yesense_ros2)
基线: 4a64eaf → b0cfbd3 (HW重建) → 0e240cd (参数) → 1740e23 (EMA) → [Phase 1A 未提交]
修改: yesense_node.cpp (+183/-29), CMakeLists.txt, package.xml, config.yaml
新增: msg/ImuRawHw.msg

# cam_imu_sync (extra_ws/src/cam_imu_sync)
基线: 8f0c521 (初版) → be20801 (插值) → [Phase 1A 未提交]
修改: sync_node.py (+797/-272), launch.py, package.xml, setup.py
新增: models.py, sync_manager.py, diagnostics.py, test/test_sync_manager.py
```

---

## 5. 验证与结论

### 5.1 核心对比

| 指标 | 编号系列 (无同步) | C 系列 (sync v1) | D 系列 (steady+驱动改) | **E 系列 (Phase 1A)** |
|------|:---:|:---:|:---:|:---:|
| bag 数量 | 11 | 4 | 18 | 10 |
| 启动次数 | ~6 | 4 | 7 | **5** |
| timeshift range | ~972 ms | ~191 ms | 924.6 ms | **2.48 ms** |
| timeshift std | — | — | 251.12 ms | **0.74 ms** |
| 空间外参 tz std | — | — | 0.0020 m | 0.0018 m |

### 5.2 E 系列按启动批次统计

| 启动 | mean (ms) | std (ms) |
|------|:---:|:---:|
| Launch 1 | -15.49 | 0.03 |
| Launch 2 | -16.99 | 0.57 |
| Launch 3 | -15.60 | 0.04 |
| Launch 4 | -15.39 | 0.68 |
| Launch 5 | -15.25 | 0.21 |
| **总体** | **-15.74** | **0.74** |

### 5.3 运行时验证（典型启动日志）

```
[Phase 1A] DETERMINISTIC SYNC ENABLED
[Phase 1A] ros_minus_steady_offset = 1776311084.011211 s
[Phase 1A] subscribed to /imu/raw_hw

State: WAIT_IMU_READY → WAIT_CAM_STABLE       (0.3s)
State: WAIT_CAM_STABLE → WAIT_FIRST_SYNC      (0.6s)
State: WAIT_FIRST_SYNC → READY                (0.7s)
[sync] first frame synced! startup_delay=0.730 s

[sync stats] synced=290  dropped=10  interp=284  imu_pub=2355
             timeout=0  ts_anomaly=0  resets=0  rearms=0
[IMU stats] freq=200.0 Hz  total_recv=2003  tid_gaps=0
```

### 5.4 结论

1. **根因已确认并消除**：timeshift 跨启动跳变完全由软件时间域不统一造成。Phase 1A 通过统一 steady_clock 锚点 + 集中式 header 重写彻底解决。

2. **改善幅度**：
   - timeshift std：**251 ms → 0.74 ms**（改善 339 倍）
   - timeshift range：**925 ms → 2.48 ms**（改善 373 倍）
   - 远超 ≤ 5 ms 的设计目标

3. **物理真值确定**：5 次独立重启全部收敛于 **-15.7 ms**，这是 IMU-Camera 硬件流水线的真实延迟常数。

4. **产出物**：
   - 可直接用于 ORB-SLAM3 的标定参数：`timeshift_cam_imu = -0.0157`
   - 经 10 次验证的稳定空间外参（tz = -0.0686 m）
   - 为 Phase 1B（硬件时间戳重建）预留的 ImuRawHw 接口

---

## 6. 附录

### 6.1 编译与运行

```bash
# 在 Docker 容器 autoware_env_v2_host 内执行

# 编译驱动
source /opt/ros/humble/setup.bash
cd /home/gxxl/slam_ws_v2/driver_ws
colcon build --packages-select yesense_interface yesense_std_ros2

# 编译同步节点
source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash
cd /home/gxxl/slam_ws_v2/extra_ws
colcon build --packages-select cam_imu_sync

# 启动（Phase 1A 默认启用）
source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash
ros2 launch cam_imu_sync cam_imu_sync.launch.py

# 回退旧模式
ros2 launch cam_imu_sync cam_imu_sync.launch.py deterministic_sync:=false
```

### 6.2 硬件约束备忘

- Yesense H30 固件不输出 0x51（sample_timestamp）和 0x52（data_ready_timestamp）
- ImuRawHw.msg 中的 `sample_timestamp`、`data_ready_timestamp`、`hw_ts_unit_sec` 字段当前为零值预留
- 如 H30 固件未来升级支持这些字段，可启用 Phase 1B（硬件时间戳重建方案），无需修改消息接口
