#!/usr/bin/env python3
"""
convert_bag_encoding.py
-----------------------
将 ROS bag 中 yuv422_yuy2 编码的图像转换为 mono8 或 rgb8 编码。

用法:
  # ROS 2 bag → mono8（默认）
  python3 convert_bag_encoding.py ros2 /path/to/input_bag /path/to/output_bag

  # ROS 2 bag → rgb8
  python3 convert_bag_encoding.py ros2 /path/to/input_bag /path/to/output_bag --encoding rgb8

  # ROS 1 bag → mono8
  python3 convert_bag_encoding.py ros1 /path/to/input.bag /path/to/output.bag

  # 只转换指定 topic
  python3 convert_bag_encoding.py ros2 /path/to/input_bag /path/to/output_bag --topics /image_raw

依赖:
  - ROS 2 模式: rosbag2_py, rclpy, sensor_msgs, numpy, cv2 (opencv)
  - ROS 1 模式: rosbag (Python 2/3), sensor_msgs, cv_bridge, numpy, cv2
"""

import argparse
import sys
import numpy as np

try:
    import cv2
except ImportError:
    print("错误: 请安装 opencv-python:  pip3 install opencv-python", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# YUV422 (YUYV / YUY2) → BGR / Gray 转换
# ---------------------------------------------------------------------------

def yuyv_to_bgr(data: bytes, height: int, width: int) -> np.ndarray:
    """将 YUYV (YUV 4:2:2) 原始字节转换为 BGR numpy 数组。"""
    yuv = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 2))
    bgr = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_YUYV)  # YUYV ↔ YUY2
    return bgr


def yuyv_to_gray(data: bytes, height: int, width: int) -> np.ndarray:
    """将 YUYV (YUV 4:2:2) 原始字节转换为单通道灰度 numpy 数组。"""
    yuv = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 2))
    gray = cv2.cvtColor(yuv, cv2.COLOR_YUV2GRAY_YUYV)
    return gray


# ---------------------------------------------------------------------------
# ROS 2 模式
# ---------------------------------------------------------------------------

def convert_ros2(input_bag: str, output_bag: str, target_encoding: str,
                 topics: list[str] | None):
    """读取 ROS 2 bag（mcap / sqlite3），转换图像编码并写入新 bag。"""
    try:
        import rosbag2_py
        from rclpy.serialization import deserialize_message, serialize_message
        from sensor_msgs.msg import Image
    except ImportError as e:
        print(f"错误: 缺少 ROS 2 依赖: {e}", file=sys.stderr)
        print("请在 ROS 2 环境中运行此脚本 (source /opt/ros/<distro>/setup.bash)",
              file=sys.stderr)
        sys.exit(1)

    # ---- 打开输入 bag ----
    reader = rosbag2_py.SequentialReader()
    storage_options = rosbag2_py.StorageOptions(uri=input_bag, storage_id="")
    converter_options = rosbag2_py.ConverterOptions(
        input_serialization_format="cdr",
        output_serialization_format="cdr",
    )
    reader.open(storage_options, converter_options)

    # 读取 topic 元数据
    topic_meta_list = reader.get_all_topics_and_types()
    image_topics = set()
    for tm in topic_meta_list:
        if tm.type == "sensor_msgs/msg/Image":
            if topics is None or tm.name in topics:
                image_topics.add(tm.name)

    if not image_topics:
        print("警告: 未找到匹配的 sensor_msgs/msg/Image topic", file=sys.stderr)

    print(f"将转换以下 topic 的编码 → {target_encoding}: {sorted(image_topics)}")

    # ---- 打开输出 bag ----
    writer = rosbag2_py.SequentialWriter()
    out_storage = rosbag2_py.StorageOptions(uri=output_bag, storage_id="sqlite3")
    writer.open(out_storage, converter_options)

    # 创建全部 topic
    for tm in topic_meta_list:
        topic_info = rosbag2_py.TopicMetadata(
            name=tm.name,
            type=tm.type,
            serialization_format=tm.serialization_format,
        )
        writer.create_topic(topic_info)

    # ---- 逐条读取并转换 ----
    count = 0
    converted = 0
    while reader.has_next():
        topic, raw_data, timestamp = reader.read_next()
        count += 1

        if topic in image_topics:
            msg = deserialize_message(raw_data, Image)
            enc_lower = msg.encoding.lower()

            if enc_lower in ("yuv422_yuy2", "yuyv", "yuy2"):
                h, w = msg.height, msg.width
                if target_encoding == "mono8":
                    img = yuyv_to_gray(bytes(msg.data), h, w)
                    msg.encoding = "mono8"
                    msg.step = w
                    msg.data = img.tobytes()
                else:  # rgb8
                    bgr = yuyv_to_bgr(bytes(msg.data), h, w)
                    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                    msg.encoding = "rgb8"
                    msg.step = w * 3
                    msg.data = rgb.tobytes()

                raw_data = serialize_message(msg)
                converted += 1

        writer.write(topic, raw_data, timestamp)

        if count % 100 == 0:
            print(f"  已处理 {count} 条消息, 已转换 {converted} 条图像 …")

    del writer  # 确保刷新
    del reader
    print(f"完成! 共处理 {count} 条消息, 转换 {converted} 条图像 → {target_encoding}")
    print(f"输出 bag: {output_bag}")


# ---------------------------------------------------------------------------
# ROS 1 模式
# ---------------------------------------------------------------------------

def convert_ros1(input_bag: str, output_bag: str, target_encoding: str,
                 topics: list[str] | None):
    """读取 ROS 1 bag，转换图像编码并写入新 bag。"""
    try:
        import rosbag
        from sensor_msgs.msg import Image as ImageMsg
    except ImportError as e:
        print(f"错误: 缺少 ROS 1 依赖: {e}", file=sys.stderr)
        print("请在 ROS 1 环境中运行此脚本 (source /opt/ros/noetic/setup.bash)",
              file=sys.stderr)
        sys.exit(1)

    # 先扫描一遍确定需要转换的 topic
    with rosbag.Bag(input_bag, "r") as bag:
        info = bag.get_type_and_topic_info()
        image_topics = set()
        for topic_name, topic_info in info.topics.items():
            if topic_info.msg_type == "sensor_msgs/Image":
                if topics is None or topic_name in topics:
                    image_topics.add(topic_name)

    if not image_topics:
        print("警告: 未找到匹配的 sensor_msgs/Image topic", file=sys.stderr)

    print(f"将转换以下 topic 的编码 → {target_encoding}: {sorted(image_topics)}")

    count = 0
    converted = 0
    with rosbag.Bag(output_bag, "w") as out_bag:
        with rosbag.Bag(input_bag, "r") as in_bag:
            for topic, msg, t in in_bag.read_messages():
                count += 1

                if topic in image_topics:
                    enc_lower = msg.encoding.lower()
                    if enc_lower in ("yuv422_yuy2", "yuyv", "yuy2"):
                        h, w = msg.height, msg.width
                        if target_encoding == "mono8":
                            img = yuyv_to_gray(bytes(msg.data), h, w)
                            msg.encoding = "mono8"
                            msg.step = w
                            msg.data = img.tobytes()
                        else:  # rgb8
                            bgr = yuyv_to_bgr(bytes(msg.data), h, w)
                            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                            msg.encoding = "rgb8"
                            msg.step = w * 3
                            msg.data = rgb.tobytes()

                        converted += 1

                out_bag.write(topic, msg, t)

                if count % 100 == 0:
                    print(f"  已处理 {count} 条消息, 已转换 {converted} 条图像 …")

    print(f"完成! 共处理 {count} 条消息, 转换 {converted} 条图像 → {target_encoding}")
    print(f"输出 bag: {output_bag}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="将 ROS bag 中 yuv422_yuy2 图像转换为 mono8 或 rgb8 (供 Kalibr 使用)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  # ROS 2 bag → mono8
  python3 convert_bag_encoding.py ros2 \\
      ../bags/cam_kalibr_01 \\
      ../bags/cam_kalibr_01_mono8

  # ROS 1 bag → rgb8
  python3 convert_bag_encoding.py ros1 \\
      ../bags/rosbags/cam_kalibr_01.bag \\
      ../bags/rosbags/cam_kalibr_01_rgb8.bag \\
      --encoding rgb8
""",
    )
    parser.add_argument("mode", choices=["ros1", "ros2"],
                        help="ROS 版本 (ros1 或 ros2)")
    parser.add_argument("input_bag", help="输入 bag 路径")
    parser.add_argument("output_bag", help="输出 bag 路径")
    parser.add_argument("--encoding", choices=["mono8", "rgb8"], default="mono8",
                        help="目标编码格式 (默认: mono8)")
    parser.add_argument("--topics", nargs="+", default=None,
                        help="只转换指定的 image topic (默认: 所有 Image topic)")

    args = parser.parse_args()

    print(f"模式: {args.mode.upper()}")
    print(f"输入: {args.input_bag}")
    print(f"输出: {args.output_bag}")
    print(f"目标编码: {args.encoding}")
    print()

    if args.mode == "ros2":
        convert_ros2(args.input_bag, args.output_bag, args.encoding, args.topics)
    else:
        convert_ros1(args.input_bag, args.output_bag, args.encoding, args.topics)


if __name__ == "__main__":
    main()
