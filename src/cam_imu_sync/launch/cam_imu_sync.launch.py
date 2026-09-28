"""Launch camera + IMU + synchronisation node.

Starts three components:
  1. usb_cam          – USB camera driver  → /image_raw
  2. yesense_std_ros2 – Yesense H30 IMU   → /imu/data_raw
  3. cam_imu_sync     – sync node          → /sync/image_raw, /sync/imu

Usage
-----
    ros2 launch cam_imu_sync cam_imu_sync.launch.py

    # with camera calibration file:
    ros2 launch cam_imu_sync cam_imu_sync.launch.py \\
        camera_info_url:=file:///path/to/camera_info.yaml

    # override time offset:
    ros2 launch cam_imu_sync cam_imu_sync.launch.py \\
        cam_imu_time_offset:=0.30

    # disable interpolation (fallback to simple forwarding):
    ros2 launch cam_imu_sync cam_imu_sync.launch.py \\
        enable_interpolation:=false
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    return LaunchDescription([
        # ── Arguments ─────────────────────────────────────────────────
        DeclareLaunchArgument(
            'cam_imu_time_offset', default_value='0.2745',
            description='Kalibr timeshift_cam_imu [s]  '
                        '(t_imu = t_cam + offset)'),
        DeclareLaunchArgument(
            'video_device', default_value='/dev/video-rmoncam',
            description='V4L2 video device path'),
        DeclareLaunchArgument(
            'camera_info_url', default_value='',
            description='Camera calibration YAML URL '
                        '(e.g. file:///path/to/camera_info.yaml)'),
        DeclareLaunchArgument(
            'enable_interpolation', default_value='true',
            description='Enable linear interpolation at frame boundaries'),

        # ── USB Camera ────────────────────────────────────────────────
        # publishes: /image_raw  (sensor_msgs/Image, RELIABLE)
        #            /camera_info (if camera_info_url is set)
        Node(
            package='usb_cam',
            executable='usb_cam_node_exe',
            name='usb_cam',
            output='screen',
            parameters=[{
                'video_device': LaunchConfiguration('video_device'),
                'image_width':  640,
                'image_height': 480,
                'framerate':    30.0,
                'pixel_format': 'yuyv',
                'camera_info_url':
                    LaunchConfiguration('camera_info_url'),
            }],
        ),

        # ── Yesense H30 IMU ──────────────────────────────────────────
        # publishes: /imu/data_raw  (sensor_msgs/Imu)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                PathJoinSubstitution([
                    FindPackageShare('yesense_std_ros2'),
                    'launch', 'yesense_node.launch.py'])),
        ),

        # ── Sync Node ────────────────────────────────────────────────
        # subscribes: /image_raw, /imu/data_raw
        # publishes:  /sync/image_raw, /sync/imu
        Node(
            package='cam_imu_sync',
            executable='sync_node',
            name='cam_imu_sync_node',
            output='screen',
            parameters=[{
                'cam_imu_time_offset':
                    LaunchConfiguration('cam_imu_time_offset'),
                'image_topic_in':  '/image_raw',
                'imu_topic_in':    '/imu/data_raw',
                'image_topic_out': '/sync/image_raw',
                'imu_topic_out':   '/sync/imu',
                'enable_interpolation':
                    LaunchConfiguration('enable_interpolation'),
            }],
        ),
    ])
