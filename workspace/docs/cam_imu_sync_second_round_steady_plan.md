# cam_imu_sync 第二轮整改方案：首帧同步与 target_align 全面切换到 steady 域

## 1. 目标

上一轮整改后，系统已经不再进入“半失锁后带病运行”的坏状态，但新日志表明问题收敛成了新的、更具体的模式：

- 有些 run 能完成第一次同步，随后全程稳定；
- 有些 run 根本无法完成第一次同步，因此全程 `sync_frames=0`；
- 同步成功与否几乎完全取决于 **camera header 时间域** 与 **IMU header 时间域** 在当前启动中的相对起始偏移。

因此，当前阶段的核心目标不是继续调整固定 offset，而是：

1. 将 **首帧同步** 完全迁移到 `steady_clock` 域；
2. 将 **target_align 的建立** 从 header 域切换到 steady 域；
3. 彻底消除“跨设备 header 时间基准随机跳变”对同步成功率的影响；
4. 在无法使用 IMU 硬件时间戳、无法修改固件的前提下，统一采用 **主机 steady 域逻辑时间轴** 完成同步。

---

## 2. 当前问题定性

### 2.1 已修复的问题

上一轮整改已经有效解决了以下问题：

- 不再出现进入 READY 后长时间 `imu_last=0` 但系统继续运行的状态；
- `WAIT_IMU_READY` 生效，IMU 管道本身已经足够稳定；
- 正常 run 中，IMU 平均周期接近 `5.000 ms`，抖动很小；
- 一旦完成第一次同步，后续 run 基本稳定。fileciteturn10file4turn10file5turn10file6turn10file7turn10file8turn10file9

### 2.2 仍未修复的问题

新日志显示，系统当前失败模式变为：

- `WAIT_IMU_READY` 通过；
- 但 `WAIT_FIRST_SYNC` 无法完成；
- 从而整轮 `sync_frames=0`，且 `timeout_count == dropped_frames`；
- 成功 run 与失败 run 的差异，不在 steady 域，而在 **header 域 camera↔IMU 相对零点跳变**。

### 2.3 根因

当前 `target_align` 的建立，仍然近似基于：

```text
 target = cam_header + offset
```

这在当前项目约束下是不可接受的，因为：

- 无法使用 IMU 协议中的硬件时间戳 `0x51/0x52`；
- 无法改固件；
- `usb_cam` 的 `header.stamp` 与 IMU 驱动内生成的 `header.stamp` 并不处在同一个可稳定比较的跨设备时间基准中；
- 不同 run 中，camera header 相对 IMU header 的起始偏移会跳变数百毫秒。

结果就是：

- 某些 run 中，`cam_header + offset` 恰好落在 IMU 已覆盖区间中，因此第一次同步成功；
- 某些 run 中，`cam_header + offset` 落到 IMU 当前时间轴前方几百毫秒，导致第一次同步永远无法满足条件。

### 2.4 关键结论

**当前问题不是状态机本身，而是首帧同步和 target_align 仍然建在错误的时间基准上。**

---

## 3. 总体整改原则

### 原则 1：首帧同步必须只用 steady 域

第一次同步是否成功，必须只取决于：

- `cam_host_steady_ns`
- `imu_host_steady_ns`

不能再依赖：

- `cam_header_ns`
- `imu_header_ns`
- 或任何由这两者直接构造的 target

### 原则 2：target_align 建议统一迁移到 steady 域

若仍让 READY 状态继续使用 header 域 target，当前问题仍会在别的形式下重新出现。

因此建议：

- **首帧同步**：强制 steady 域；
- **后续 READY 帧同步**：也统一使用 steady 域；
- `header.stamp` 仅保留为观测字段，不再作为同步主判据。

### 原则 3：offset 必须定义在 steady 域

原先 `sync_offset_param=0.274500` 若语义来自 header 域，需要重新定义为：

```text
steady_cam_to_imu_offset_sec
```

即：

- camera 主机接收时间相对 IMU 主机时间的经验偏移；
- 由 steady 域实验结果驱动，而不是 header 域实验结果驱动。

---

## 4. Driver 层整改措施

Driver 层本轮不需要大改，只做最小补充与约束强化。

---

### 4.1 保持现有 steady 打点方案，不得回退到 header 打点主导

#### 要求

IMU 驱动一旦完成一帧协议解析，必须立刻记录：

```cpp
imu_host_steady_ns = steady_clock_now_ns();
```

此字段继续作为：

- sync 包主消费时间戳；
- 同步区间构建依据；
- steady 域日志主判据。

#### 禁止

- 不能以 `imu.header.stamp` 反向覆盖 `imu_host_steady_ns`；
- 不能在 publish 之后再打 steady 时间；
- 不能让 sync 包读取“晚于实际接收时刻”的 IMU 时间。

---

### 4.2 对外提供明确的 IMU steady 时间字段

#### 要做的事

Driver 层对 sync 包输出的 IMU 数据结构中，必须显式包含：

- `imu_host_steady_ns`
- `imu_seq`
- `ax, ay, az`
- `gx, gy, gz`

#### 目的

避免 sync 包内部再次从 ROS header 中推导时间。

---

### 4.3 保留 header 仅作观测字段

#### 要做的事

可以保留：

- `imu_header_ns`

但它只能用于日志分析，不能参与同步判据。

#### 目的

帮助后续继续观察驱动行为，但不让不稳定 header 域污染同步逻辑。

---

### 4.4 Driver reset/restart 逻辑保持现有做法

保留上一轮要求：

- 串口打开后 flush
- warm-up 丢前若干 IMU
- reset 时清空内部 buffer 和统计状态

本轮不要求额外新增复杂逻辑。

---

## 5. Sync 包整改措施

这是本轮整改重点。

---

## 5.1 `WAIT_FIRST_SYNC` 必须完全切换到 steady 域

### 当前错误模式

当前第一次同步实际仍依赖 header 域 target，因此成功与否受 camera header 起始偏移影响。

### 新要求

在 `WAIT_FIRST_SYNC` 状态下，所有判据必须只使用：

- `cam_host_steady_ns`
- `latest_imu_host_steady_ns`
- `imu_buffer` 中的 steady 时间

### 首帧 target 定义

将首帧 target 改为：

```text
target_steady = cam_host_steady + steady_cam_to_imu_offset
```

其中：

- `steady_cam_to_imu_offset` 为 steady 域经验参数；
- 不再使用 `cam_header + header_offset`。

---

## 5.2 新增 steady 域 offset 参数

### 要做的事

把当前 offset 参数改名或新增新参数：

```yaml
steady_cam_to_imu_offset_sec: 0.05
```

### 参数语义

含义为：

- 从 camera 主机接收时刻映射到同步目标时刻时，所添加的 steady 域偏移；
- 该值通常应远小于旧 header 域里的 `0.2745 s`；
- 由 steady 实验数据重新估计。

### 说明

根据之前正常 run 的 steady 实验，稳定运行时：

- `cam_minus_imu_last` 在几十毫秒量级；
- 因此此处 offset 应当重新基于 steady 域调试，而不是沿用旧 header 域经验值。

---

## 5.3 首帧同步成功条件改写

### 旧逻辑问题

旧逻辑本质上在问：

> “IMU 是否覆盖到了 `cam_header + offset`？”

这个问题本身建立在不稳定时间域上。

### 新逻辑

首帧同步时，改为判断：

1. 是否存在图像帧；
2. 是否存在足够新的 IMU 样本；
3. `latest_imu_steady >= target_steady + safety_margin`；
4. 能否找到一个合法的 `imu_last_steady <= target_steady`。

### 成功后动作

第一次同步成功后：

```cpp
_prev_aligned_steady_t = target_steady;
_first_sync_done = true;
_state = READY;
```

注意：

- `_prev_aligned_t` 现在也必须是 steady 域变量；
- 不能再混用 header 域 prev。

---

## 5.4 READY 状态下的全部同步也统一切到 steady 域

### 要做的事

在 READY 状态下，对每一帧图像：

```text
target_steady = cam_host_steady + steady_cam_to_imu_offset
```

然后在 IMU buffer 中构建区间：

```text
(prev_aligned_steady_t, target_steady]
```

### 必须使用的字段

- `imu_first_steady_ns`
- `imu_last_steady_ns`
- `target_align_steady_ns`

### 禁止

- 不允许 READY 状态重新退回使用 `cam_header_ns` 主导 target；
- 不允许同时维护一套 header target 和一套 steady target；
- 不允许输出时再按 header 重打同步判据。

---

## 5.5 插值也必须在 steady 域时间轴上完成

### 要做的事

如果在 `target_steady` 处需要插值：

- 使用 `imu_prev_steady` 和 `imu_next_steady` 两个样本；
- 以 `target_steady` 为插值时间；
- 线性插值 `gyro/accel`。

### 插值公式

```text
alpha = (target_steady - t0) / (t1 - t0)
x_target = (1-alpha) * x0 + alpha * x1
```

### 说明

插值时间轴和同步区间时间轴必须一致，不能：

- 区间在 steady 域，插值却用 header 域；
- 或 target_steady 确立后，再拿 header 去重算 alpha。

---

## 5.6 `header.stamp` 不再参与首帧同步与 READY 判定

### 要做的事

保留以下字段做观测：

- `cam_header_ns`
- `imu_header_ns`

但以下逻辑中不得使用：

- 首帧是否可同步
- 是否覆盖到 target
- 区间裁剪
- 插值时间
- 失锁判定

### 目的

彻底切断 header 域对同步成功率的影响。

---

## 5.7 `WAIT_FIRST_SYNC` 增加超时 re-arm 机制

### 背景

当前失败 run 会整轮停在 `WAIT_FIRST_SYNC`，最终 `sync_frames=0`。

### 新要求

若在 `WAIT_FIRST_SYNC` 中持续超时，例如：

- 连续等待超过 `first_sync_timeout_sec`；
- 或连续丢弃超过 `N` 帧图像；

则执行：

1. 清空图像等待队列；
2. 保留当前 IMU buffer 中较新部分，或按实现重新等待 IMU ready；
3. 回退到 `WAIT_IMU_READY`；
4. 重新建立第一次同步。

### 建议参数

```yaml
first_sync_timeout_sec: 2.0
first_sync_drop_limit: 60
```

---

## 5.8 READY 状态健康监测改为 steady 域主判据

### 要监控的指标

- `cam_minus_imu_last_steady_ns`
- `imu_count`
- `imu_last_exists`
- `latest_imu_steady - target_steady`

### 建议规则

若连续若干帧出现：

- `imu_last == 0`
- 或 `cam_minus_imu_last_steady_ms > 100 ms`
- 或 `latest_imu_steady < target_steady`

则视为失锁，执行：

- 不发布本帧；
- 不更新 `prev_aligned_steady_t`；
- 连续失败计数加 1；
- 超过阈值则回到 `WAIT_IMU_READY`。

### 目的

避免 READY 状态再次悄悄回到“看起来活着但其实错配”的旧状态。

---

## 5.9 输出消息时间戳策略建议

### 建议做法

即使对外 ROS 消息仍需要 `header.stamp`，内部同步仍以 steady 域为主。

可以采用两层时间：

- **内部同步时间轴**：`steady_ns`
- **对外 ROS header**：保留现有系统要求的时间格式

### 关键原则

对外 header 如何填写可以后续再调，但内部是否同步成功，必须只看 steady 域。

---

## 5.10 诊断日志模板统一升级

### 要输出的关键字段

在 `SYNC_OUT` 中固定输出：

```text
type=SYNC_OUT
run_id=...
cam_frame_id=...
cam_host_steady_ns=...
target_align_steady_ns=...
imu_first_id=...
imu_last_id=...
imu_count=...
imu_first_steady_ns=...
imu_last_steady_ns=...
cam_minus_imu_last_steady_ns=...
interp_used=...
```

### 说明

后续只用这几项判断同步成败；
`cam_header_ns` / `imu_header_ns` 仅作为附加观察项。

---

## 6. 建议参数默认值

```yaml
steady_cam_to_imu_offset_sec: 0.05
first_sync_safety_margin_ms: 5.0
first_sync_timeout_sec: 2.0
first_sync_drop_limit: 60
sync_fail_lag_threshold_ms: 100.0
sync_fail_consecutive_limit: 5
```

### 说明

- 这里的 `0.05 s` 只是 steady 域起始建议值；
- 最终仍需基于新 steady 日志微调；
- 但必须明确：这个 offset 现在是 **steady 域 offset**，不是旧 header 域 offset。

---

## 7. 建议的伪代码

### 7.1 WAIT_FIRST_SYNC

```cpp
if (state == WAIT_FIRST_SYNC) {
    if (!has_image()) return;

    auto cam = peek_image();
    double cam_t = cam.host_steady_sec;
    double target_t = cam_t + steady_cam_to_imu_offset_sec;

    if (latest_imu_steady_sec < target_t + first_sync_safety_margin_sec) {
        register_first_sync_wait();
        if (first_sync_wait_too_long()) {
            rearm_to_wait_imu_ready();
        }
        return;
    }

    auto last_imu = find_last_imu_before(target_t);
    if (!last_imu.valid) {
        register_first_sync_wait();
        if (first_sync_wait_too_long()) {
            rearm_to_wait_imu_ready();
        }
        return;
    }

    publish_first_sync(cam, last_imu, target_t);
    prev_aligned_steady_t = target_t;
    first_sync_done = true;
    state = READY;
    pop_image();
    reset_fail_counter();
    return;
}
```

### 7.2 READY

```cpp
if (state == READY) {
    if (!has_image()) return;

    auto cam = peek_image();
    double cam_t = cam.host_steady_sec;
    double target_t = cam_t + steady_cam_to_imu_offset_sec;

    if (latest_imu_steady_sec < target_t) {
        register_fail();
        if (fail_count >= sync_fail_consecutive_limit) {
            rearm_to_wait_imu_ready();
        }
        return;
    }

    ImuInterval interval;
    if (!build_interval_steady(prev_aligned_steady_t, target_t, interval)) {
        register_fail();
        if (fail_count >= sync_fail_consecutive_limit) {
            rearm_to_wait_imu_ready();
        }
        return;
    }

    if (need_interpolation(interval, target_t)) {
        interpolate_steady(interval, target_t);
    }

    publish_sync(interval, cam, target_t);
    prev_aligned_steady_t = target_t;
    pop_image();
    reset_fail_counter();
    return;
}
```

---

## 8. agent 实施清单

### 8.1 Driver 层

- [ ] 保持 `imu_host_steady_ns` 为 sync 主消费时间
- [ ] 确认打点位置仍在“整帧确认后立即执行”
- [ ] IMU 输出结构中显式保留 `imu_host_steady_ns`
- [ ] 保留 `imu_header_ns` 仅用于日志
- [ ] 不允许 sync 从 IMU header 推导主时间轴

### 8.2 Sync 包

- [ ] `WAIT_FIRST_SYNC` 全面改用 steady 域
- [ ] 新增 `steady_cam_to_imu_offset_sec`
- [ ] `_prev_aligned_t` 替换为 `_prev_aligned_steady_t`
- [ ] READY 状态同步区间全部改为 steady 域区间
- [ ] 插值时间轴统一改为 steady 域
- [ ] header 域不再参与首帧同步、READY 判定、失锁判定
- [ ] 增加 `WAIT_FIRST_SYNC` 超时 re-arm
- [ ] READY 健康监测以 `cam_minus_imu_last_steady_ns` 为主判据
- [ ] 统一日志输出 steady 域关键字段

---

## 9. 验收标准

完成本轮整改后，应满足：

1. 连续 5 次独立启动，不再出现“一部分 run `sync_frames=0`，一部分 run 全正常”的二值化现象；
2. `WAIT_FIRST_SYNC` 能稳定完成，不再被 header 域起始偏移决定成败；
3. READY 状态下：
   - steady 域 `cam_minus_imu_last_mean_ms` 稳定在几十毫秒量级；
   - `std` 保持较小；
4. 不再需要依赖 `cam_header_ns - imu_header_ns` 来判断同步成败；
5. 同步成败完全可由 steady 域日志解释。

---

## 10. 结论

当前系统已经从“启动后半失锁”进化到了“首帧能否成功取决于 header 域是否碰巧对上”。

这说明：

- 上一轮状态机整改是有效的；
- 真正剩余的问题已经缩小到一个非常明确的点：

**首帧同步和 target_align 仍然建在错误的时间基准上。**

在当前约束下：

- 不能改固件；
- 用不上 IMU 硬件时间戳；
- header 域跨设备不可稳定比较；

因此，下一步必须把：

- 首帧同步
- target_align 建立
- READY 区间同步
- 插值时间轴
- 失锁判定

全部统一切换到 **steady 域**。

只有这样，系统才能真正摆脱“某些 run 全正常、某些 run 0 帧”的随机启动命运。
