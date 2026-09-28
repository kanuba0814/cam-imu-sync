# IMU-Camera 确定性时间同步：技术摘要

**问题**：每次重启后，Kalibr 标定出的 timeshift 在 -213 ms ~ +711 ms 间随机跳变（std = 251 ms），同一次启动内却极稳（std < 1.2 ms）。空间外参不受影响。

**根因**：IMU 驱动和 Camera 驱动各自独立调用 `ros::now()` 打时间戳，两者在启动时的调用时机差是随机的 —— 每次重启都给两条数据流引入一个不同的时间偏移。

---

## 改了什么

### 1. IMU 驱动（yesense_node.cpp）

新增一个 `ImuRawHw` 消息类型，在原有 `sensor_msgs/Imu` 之外额外发布到 `/imu/raw_hw`。关键区别：

```cpp
// 帧解码确认时刻，同时抓两个时钟
auto host_steady_now = std::chrono::steady_clock::now();  // 单调时钟
auto ros_now = this->get_clock()->now();                   // ROS 时钟

raw_hw.rx_steady_ns = host_steady_now;  // ← 这是同步的唯一依据
raw_hw.rx_ros_ns    = ros_now;          // 仅诊断用
raw_hw.tid          = result->tid;      // 协议序列号，用于丢包检测
```

`steady_clock` 是 Linux 的单调时钟，从开机起单调递增，不受 NTP/系统时间调整影响。它不关心"现在几点"，只关心"距上次过了多久" —— 所以两个传感器用同一个 `steady_clock` 打戳，就天然处于同一时间轴。

### 2. 同步节点（cam_imu_sync）

启动时**一次性**捕获 ROS 时钟与 steady_clock 的差值，之后再也不变：

```python
# 启动时执行一次
offset = (ros_now_ns - steady_now_ns) / 1e9   # 例如 1776311084.011 s
```

之后所有输出消息（IMU + Image）的 `header.stamp` 全部由同一个函数生成：

```python
def steady_ns_to_ros_sec(steady_ns):
    return steady_ns / 1e9 + offset
```

Camera 帧到达时记录 `time.monotonic_ns()`（Python 版 steady_clock），IMU 用驱动传来的 `rx_steady_ns`。两者经同一个 `offset` 映射回 ROS 时间域 —— **时间锚点唯一，不再随机。**

### 3. 发布前重写

所有 header 重写在 `publish()` 之前完成（修复了原来"先发布再改戳"的 bug）：

```
IMU steady_ns  ──→ steady_ns_to_ros_sec() ──→ 改写 header.stamp ──→ publish
CAM steady_ns  ──→ steady_ns_to_ros_sec() ──→ 改写 header.stamp ──→ publish
```

---

## 效果

| 指标 | 无同步（手动启动） | 改造后（E 系列） |
|------|:-:|:-:|
| 启动次数 | ~6 | 5 |
| timeshift 范围 | ~972 ms（+20 ~ +993） | **2.5 ms** |
| timeshift 分布 | 完全随机，正负不定 | **收敛于 -15.7 ms** |
| 同启动内一致性 | 好（std < 1 ms） | 好（std < 1 ms） |
| 跨启动一致性 | 不可用 | **std = 0.74 ms** |

改造前手动启动两个传感器，每次 Kalibr 标出的 timeshift 在将近 1 秒的范围内随机跳——标定结果完全不可用，每次重启都得重新标。改造后 5 次独立重启全部收敛在 -15.7 ms，这就是硬件流水线的真实延迟，可以直接写进 ORB-SLAM3 配置。

一句话：用 `steady_clock` 统一了时间源，消灭了启动时的随机锚点差异。
