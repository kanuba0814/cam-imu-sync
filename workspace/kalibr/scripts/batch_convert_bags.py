#!/usr/bin/env python3
"""
batch_convert_bags.py
---------------------
批量将 ROS 2 bag 中的图像话题转换为 mono8 (或 rgb8) 编码，
然后（可选）转换为 ROS 1 格式 (.bag) 输出到指定目录。

基于 convert_bag_encoding.py 的转换逻辑，增加了：
  - glob 模式批量匹配多个 bag
  - 自动转换为 ROS 1 格式 (通过 rosbags-convert)
  - 可自定义输出目录 (--dst)
  - 支持跳过已存在的输出文件 (--skip-existing)
  - 支持只进行编码转换不转 ROS1 (--no-ros1)
  - 在转换完成后可选清理中间文件 (--clean)

用法示例:
  # 批量处理 imu_cam_kalibr_D* 系列，输出 ROS1 bag 到 ./rosbags/
  python3 batch_convert_bags.py 'imu_cam_kalibr_D*'

  # 指定源目录和目标目录
  python3 batch_convert_bags.py 'imu_cam_kalibr_D*' --src ../bags --dst /tmp/output

  # 多个 glob 模式
  python3 batch_convert_bags.py 'imu_cam_kalibr_D*' 'cam_kalibr_*'

  # 跳过已处理的、清理中间文件
  python3 batch_convert_bags.py 'imu_cam_kalibr_D*' --skip-existing --clean

  # 只转编码，不转 ROS1
  python3 batch_convert_bags.py 'imu_cam_kalibr_D*' --no-ros1

依赖:
  - rosbag2_py, rclpy, sensor_msgs, numpy, cv2 (opencv)
  - rosbags (pip3 install rosbags)  — 用于 ROS2→ROS1 转换
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# 导入 convert_bag_encoding 中的核心转换函数
# ---------------------------------------------------------------------------

# 将本脚本所在目录加入 path，以便导入同目录下的 convert_bag_encoding
_script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_script_dir))

try:
    from convert_bag_encoding import convert_ros2
except ImportError:
    print("错误: 无法导入 convert_bag_encoding.py，请确保它在同一目录下",
          file=sys.stderr)
    sys.exit(1)


def find_bags(patterns: list[str], src_dir: str,
              exclude_suffixes: tuple[str, ...] = ("_mono", "_rgb")) -> list[Path]:
    """根据 glob 模式在 src_dir 下查找 ROS 2 bag 目录。

    ROS 2 bag 目录的特征是包含 metadata.yaml 文件。
    自动排除名称以 exclude_suffixes 结尾的目录（已转换过的中间产物）。
    """
    src = Path(src_dir).resolve()
    matched = set()

    for pattern in patterns:
        full_pattern = str(src / pattern)
        for match in glob.glob(full_pattern):
            p = Path(match)
            if p.is_dir() and (p / "metadata.yaml").exists():
                # 跳过已转换的中间产物
                if any(p.name.endswith(s) for s in exclude_suffixes):
                    continue
                matched.add(p)

    return sorted(matched)


def run_rosbags_convert(input_bag: Path, output_bag: Path) -> bool:
    """使用 rosbags-convert 将 ROS 2 bag 转换为 ROS 1 .bag 格式。

    Args:
        input_bag: ROS 2 bag 目录路径
        output_bag: 输出的 .bag 文件路径

    Returns:
        转换是否成功
    """
    # rosbags-convert 需要 --src 和 --dst 参数
    # 输出路径以 .bag 结尾时自动生成 ROS 1 格式
    cmd = [
        "rosbags-convert",
        "--src", str(input_bag),
        "--dst", str(output_bag),
    ]
    print(f"  执行: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 分钟超时
        )
        if result.returncode != 0:
            print(f"  ✗ rosbags-convert 失败:", file=sys.stderr)
            if result.stderr:
                print(f"    {result.stderr.strip()}", file=sys.stderr)
            return False
        if result.stdout:
            print(f"    {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("  ✗ 未找到 rosbags-convert 命令，请安装: pip3 install rosbags",
              file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print("  ✗ rosbags-convert 超时 (>10min)", file=sys.stderr)
        return False


def format_duration(seconds: float) -> str:
    """格式化持续时间为人类可读字符串。"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m{secs:.0f}s"
    hours = int(minutes // 60)
    mins = minutes % 60
    return f"{hours}h{mins}m{secs:.0f}s"


def main():
    parser = argparse.ArgumentParser(
        description="批量将 ROS 2 bag 图像编码转换为 mono8/rgb8，并可选转为 ROS 1 格式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  # 批量处理 D 系列 bag，输出到 ./rosbags/
  python3 batch_convert_bags.py 'imu_cam_kalibr_D*'

  # 指定源目录和目标目录
  python3 batch_convert_bags.py 'imu_cam_kalibr_D*' --src /path/to/bags --dst /path/to/output

  # 多个 glob 模式
  python3 batch_convert_bags.py 'imu_cam_kalibr_D*' 'cam_kalibr_*'

  # 跳过已存在的输出、转完后清理中间文件
  python3 batch_convert_bags.py 'imu_cam_kalibr_D*' --skip-existing --clean

  # 只转编码不转 ROS1 格式
  python3 batch_convert_bags.py 'imu_cam_kalibr_D*' --no-ros1

  # 使用 rgb8 编码
  python3 batch_convert_bags.py 'imu_cam_kalibr_D*' --encoding rgb8
""",
    )
    parser.add_argument(
        "patterns", nargs="+",
        help="Glob 模式，匹配 ROS 2 bag 目录名 (如 'imu_cam_kalibr_D*')",
    )
    parser.add_argument(
        "--src", default=None,
        help="ROS 2 bag 所在源目录 (默认: 脚本上两级目录下的 bags/，即 ../../bags/)",
    )
    parser.add_argument(
        "--dst", default=None,
        help="输出目录 (默认: 运行目录下的 rosbags/ 子目录)",
    )
    parser.add_argument(
        "--encoding", choices=["mono8", "rgb8"], default="mono8",
        help="目标编码格式 (默认: mono8)",
    )
    parser.add_argument(
        "--suffix", default=None,
        help="编码转换后的 bag 目录后缀 (默认: _mono 或 _rgb，根据 encoding 决定)",
    )
    parser.add_argument(
        "--topics", nargs="+", default=None,
        help="只转换指定的 image topic (默认: 所有 Image topic)",
    )
    parser.add_argument(
        "--no-ros1", action="store_true",
        help="只做编码转换，不转为 ROS 1 格式",
    )
    parser.add_argument(
        "--skip-existing", action="store_true",
        help="如果输出文件已存在则跳过",
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="转换完成后删除中间的 ROS 2 mono8 bag (仅在 ROS1 转换成功后)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只显示将要执行的操作，不实际执行",
    )

    args = parser.parse_args()

    # ---- 确定源目录 ----
    if args.src:
        src_dir = args.src
    else:
        # 默认: 脚本所在目录的上两级 / bags
        src_dir = str(_script_dir.parent.parent / "bags")

    # ---- 确定目标目录 ----
    if args.dst:
        dst_dir = Path(args.dst).resolve()
    else:
        dst_dir = Path.cwd() / "rosbags"

    # ---- 确定后缀 ----
    if args.suffix:
        suffix = args.suffix
    else:
        suffix = "_mono" if args.encoding == "mono8" else "_rgb"

    # ---- 查找匹配的 bag ----
    bags = find_bags(args.patterns, src_dir)

    if not bags:
        print(f"错误: 在 {src_dir} 下未找到匹配 {args.patterns} 的 ROS 2 bag 目录",
              file=sys.stderr)
        print("提示: ROS 2 bag 目录需包含 metadata.yaml 文件", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)
    print(f"批量 ROS 2 Bag 编码转换")
    print(f"=" * 70)
    print(f"源目录:     {src_dir}")
    print(f"目标目录:   {dst_dir}")
    print(f"目标编码:   {args.encoding}")
    print(f"转 ROS1:    {'否' if args.no_ros1 else '是'}")
    print(f"跳过已有:   {'是' if args.skip_existing else '否'}")
    print(f"清理中间:   {'是' if args.clean else '否'}")
    print(f"匹配到 {len(bags)} 个 bag:")
    for b in bags:
        print(f"  - {b.name}")
    print("=" * 70)

    if args.dry_run:
        print("\n[DRY RUN] 以下为将要执行的操作:\n")
        for bag in bags:
            mono_name = bag.name + suffix
            mono_path = bag.parent / mono_name
            print(f"  1. 编码转换: {bag.name} → {mono_name}")
            if not args.no_ros1:
                ros1_name = mono_name + ".bag"
                ros1_path = dst_dir / ros1_name
                print(f"  2. ROS1 转换: {mono_name} → {ros1_path}")
            print()
        return

    # ---- 创建输出目录 ----
    if not args.no_ros1:
        dst_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n输出目录已就绪: {dst_dir}\n")

    # ---- 批量处理 ----
    total_start = time.time()
    results = []  # (bag_name, status, duration)

    for i, bag in enumerate(bags, 1):
        bag_start = time.time()
        bag_name = bag.name
        mono_name = bag_name + suffix
        mono_path = bag.parent / mono_name

        print(f"\n{'─' * 70}")
        print(f"[{i}/{len(bags)}] 处理: {bag_name}")
        print(f"{'─' * 70}")

        # -- Step 1: 编码转换 (ROS2 yuv422 → mono8/rgb8) --
        if args.skip_existing and mono_path.exists() and (mono_path / "metadata.yaml").exists():
            print(f"  ⏭ 编码转换: {mono_name} 已存在，跳过")
        else:
            print(f"  ▶ 编码转换: {bag_name} → {mono_name}")
            try:
                convert_ros2(
                    input_bag=str(bag),
                    output_bag=str(mono_path),
                    target_encoding=args.encoding,
                    topics=args.topics,
                )
                print(f"  ✓ 编码转换完成: {mono_name}")
            except Exception as e:
                print(f"  ✗ 编码转换失败: {e}", file=sys.stderr)
                results.append((bag_name, "编码转换失败", time.time() - bag_start))
                continue

        # -- Step 2: ROS2 → ROS1 转换 --
        if args.no_ros1:
            results.append((bag_name, "✓ 编码转换完成", time.time() - bag_start))
            continue

        ros1_name = mono_name + ".bag"
        ros1_path = dst_dir / ros1_name

        if args.skip_existing and ros1_path.exists():
            print(f"  ⏭ ROS1 转换: {ros1_name} 已存在，跳过")
            results.append((bag_name, "✓ 已跳过(已存在)", time.time() - bag_start))
            continue

        print(f"  ▶ ROS1 转换: {mono_name} → {ros1_path}")
        success = run_rosbags_convert(mono_path, ros1_path)

        if success:
            print(f"  ✓ ROS1 转换完成: {ros1_name}")

            # 清理中间文件
            if args.clean and mono_path.exists():
                print(f"  🗑 清理中间文件: {mono_name}")
                shutil.rmtree(mono_path)

            results.append((bag_name, "✓ 全部完成", time.time() - bag_start))
        else:
            results.append((bag_name, "✗ ROS1转换失败", time.time() - bag_start))

    # ---- 汇总 ----
    total_duration = time.time() - total_start
    print(f"\n{'=' * 70}")
    print(f"批量处理完成! 总耗时: {format_duration(total_duration)}")
    print(f"{'=' * 70}")
    print(f"{'Bag 名称':<35} {'状态':<20} {'耗时':<10}")
    print(f"{'─' * 65}")
    for name, status, duration in results:
        print(f"{name:<35} {status:<20} {format_duration(duration):<10}")

    # 统计
    success_count = sum(1 for _, s, _ in results if s.startswith("✓"))
    fail_count = len(results) - success_count
    print(f"\n成功: {success_count}, 失败: {fail_count}, 总计: {len(results)}")

    if not args.no_ros1:
        print(f"输出目录: {dst_dir}")

    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
