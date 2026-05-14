"""Launch camera + IMU + synchronisation node.

Starts three components:
  1. usb_cam          – USB camera driver  → /image_raw
  2. yesense_std_ros2 – Yesense H30 IMU   → /imu/data_raw, /imu/raw_hw
  3. cam_imu_sync     – sync node          → /sync/image_raw,
                                              /sync/imu,
                                              /sync/imu_batch

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

    # fixed-rate IMU output:
    ros2 launch cam_imu_sync cam_imu_sync.launch.py \\
        resampled_imu_rate_hz:=100.0 \\
        publish_batch_imu:=false

    # tune sync-wait timeout:
    ros2 launch cam_imu_sync cam_imu_sync.launch.py \\
        max_sync_wait_ms:=200
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
            'cam_imu_time_offset', default_value='0.0',
            description='Header-domain offset applied to output image stamp. '
                        'Set to 0.0 when downstream (e.g. ORB-SLAM3) applies '
                        'its own cam_imu_time_offset.  Sync decisions use '
                        'steady_cam_to_imu_offset_sec instead.'),
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
        DeclareLaunchArgument(
            'enable_resampled_imu', default_value='true',
            description='Enable fixed-rate resampled IMU output'),
        DeclareLaunchArgument(
            'resampled_imu_topic', default_value='/sync/imu',
            description='Fixed-rate IMU output topic'),
        DeclareLaunchArgument(
            'resampled_imu_rate_hz', default_value='100.0',
            description='Fixed output IMU rate, e.g. 100.0 or 150.0'),
        DeclareLaunchArgument(
            'resampled_imu_latency_ms', default_value='20.0',
            description='Resampler latency to keep future samples '
                        'available for interpolation'),
        DeclareLaunchArgument(
            'resampled_imu_max_gap_ms', default_value='15.0',
            description='Maximum raw-IMU bracket gap for resampling'),
        DeclareLaunchArgument(
            'resampled_imu_threaded_publish', default_value='true',
            description='Publish fixed-rate IMU from a dedicated thread'),
        DeclareLaunchArgument(
            'publish_batch_imu', default_value='false',
            description='Publish legacy camera-window IMU batch output'),
        DeclareLaunchArgument(
            'batch_imu_topic', default_value='/sync/imu_batch',
            description='Legacy burst-style IMU batch topic'),
        # §12 / §13 arguments
        DeclareLaunchArgument(
            'max_sync_wait_ms', default_value='100.0',
            description='§13.1 – max milliseconds to wait for IMU '
                        'before dropping a queued image frame'),
        DeclareLaunchArgument(
            'max_interp_gap_ms', default_value='10.0',
            description='§13.3 – refuse interpolation when gap between '
                        'bracketing IMU samples exceeds this (ms)'),
        DeclareLaunchArgument(
            'drop_frame_on_missing_imu', default_value='true',
            description='§13.1 – drop image on sync-wait timeout'),
        DeclareLaunchArgument(
            'warn_on_queue_backlog', default_value='true',
            description='§13.5 – warn when image queue exceeds 70%'),
        DeclareLaunchArgument(
            'debug_enable', default_value='false',
            description='Enable structured terminal diagnostics output'),
        DeclareLaunchArgument(
            'debug_trace_samples', default_value='false',
            description='Print per-sample trace logs in addition to summary'),
        DeclareLaunchArgument(
            'debug_expected_imu_rate_hz', default_value='0.0',
            description='Expected IMU rate for debug consistency checks'),
        DeclareLaunchArgument(
            'executor_threads', default_value='8',
            description='MultiThreadedExecutor worker thread count'),

        # ── NEW: state-machine arguments ──────────────────────────────
        DeclareLaunchArgument(
            'camera_startup_drop_sec', default_value='1.0',
            description='§5.8 – discard camera frames for this duration '
                        'after startup'),
        DeclareLaunchArgument(
            'sync_wait_imu_ready_min_samples', default_value='40',
            description='§5.2 – minimum IMU samples for pipeline ready'),
        DeclareLaunchArgument(
            'sync_wait_imu_ready_min_span_ms', default_value='150.0',
            description='§5.2 – minimum time span (ms) for pipeline ready'),
        DeclareLaunchArgument(
            'sync_wait_imu_ready_max_std_ms', default_value='1.0',
            description='§5.2 – maximum period std-dev (ms) for ready'),
        DeclareLaunchArgument(
            'first_sync_safety_margin_ms', default_value='5.0',
            description='§5.3 – extra margin (ms) for first sync'),
        DeclareLaunchArgument(
            'sync_fail_lag_threshold_ms', default_value='100.0',
            description='§5.6 – lag threshold (ms) for sync failure'),
        DeclareLaunchArgument(
            'sync_fail_consecutive_limit', default_value='5',
            description='§5.6 – consecutive failures before re-arm'),
        DeclareLaunchArgument(
            'imu_pipeline_ready_topic', default_value='/imu/pipeline_ready',
            description='Topic for external IMU pipeline ready signal '
                        '(方案 B)'),

        # ── NEW: steady-domain arguments ──────────────────────────────
        DeclareLaunchArgument(
            'steady_cam_to_imu_offset_sec', default_value='0.05',
            description='Steady-domain cam-to-IMU offset (s). '
                        'target_steady = cam_steady + offset'),
        DeclareLaunchArgument(
            'first_sync_timeout_sec', default_value='2.0',
            description='Max wait in WAIT_FIRST_SYNC before re-arm (s)'),
        DeclareLaunchArgument(
            'first_sync_drop_limit', default_value='60',
            description='Max dropped frames in WAIT_FIRST_SYNC before '
                        're-arm'),

        # ── Phase 1A: deterministic sync arguments ────────────────────
        DeclareLaunchArgument(
            'deterministic_sync', default_value='true',
            description='Phase 1A: enable deterministic time sync '
                        '(unified steady-domain). Set false for legacy.'),
        DeclareLaunchArgument(
            'imu_raw_hw_topic', default_value='/imu/raw_hw',
            description='Phase 1A: ImuRawHw topic from yesense driver'),
        DeclareLaunchArgument(
            'raw_hw_qos_depth', default_value='1000',
            description='Phase 1A: keep-last depth for '
                        '/imu/raw_hw input'),
        DeclareLaunchArgument(
            'raw_hw_qos_reliability', default_value='best_effort',
            description='Phase 1A: /imu/raw_hw input reliability '
                        '(best_effort or reliable)'),
        DeclareLaunchArgument(
            'legacy_imu_qos_depth', default_value='50',
            description='Legacy mode: BEST_EFFORT keep-last depth for '
                        '/imu/data_raw input'),
        DeclareLaunchArgument(
            'yesense_imu_qos_depth', default_value='1000',
            description='Yesense publisher keep-last depth for '
                        '/imu/data_raw'),
        DeclareLaunchArgument(
            'yesense_imu_qos_reliability', default_value='best_effort',
            description='Yesense /imu/data_raw reliability '
                        '(best_effort or reliable)'),
        DeclareLaunchArgument(
            'yesense_raw_hw_qos_depth', default_value='1000',
            description='Yesense publisher keep-last depth for '
                        '/imu/raw_hw'),
        DeclareLaunchArgument(
            'yesense_raw_hw_qos_reliability', default_value='best_effort',
            description='Yesense /imu/raw_hw reliability '
                        '(best_effort or reliable)'),
        DeclareLaunchArgument(
            'yesense_publish_queue_depth', default_value='4000',
            description='Yesense serial-to-ROS publish queue depth'),
        DeclareLaunchArgument(
            'yesense_ros_imu_publish_queue_depth', default_value='4000',
            description='Yesense /imu/data_raw async queue depth'),
        DeclareLaunchArgument(
            'yesense_legacy_publish_queue_depth', default_value='4000',
            description='Yesense non-critical legacy topic queue depth'),
        DeclareLaunchArgument(
            'yesense_realtime_thread_priority', default_value='0',
            description='Optional SCHED_FIFO priority for Yesense '
                        'serial/raw_hw threads; 0 disables it'),
        DeclareLaunchArgument(
            'enable_header_rewrite', default_value='true',
            description='Phase 1A: rewrite all output header.stamp '
                        'from unified time domain'),
        DeclareLaunchArgument(
            'min_stable_cam_frames', default_value='10',
            description='Phase 1A: stable camera frames for '
                        'WAIT_CAM_STABLE transition'),
        DeclareLaunchArgument(
            'cam_stable_max_std_ms', default_value='10.0',
            description='Phase 1A: max camera period std-dev (ms) '
                        'for stability check'),

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
        #            /imu/pipeline_ready  (std_msgs/Bool)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                PathJoinSubstitution([
                    FindPackageShare('yesense_std_ros2'),
                    'launch', 'yesense_node.launch.py'])),
            launch_arguments={
                'debug_enable': LaunchConfiguration('debug_enable'),
                'debug_trace_samples':
                    LaunchConfiguration('debug_trace_samples'),
                'debug_expected_imu_rate_hz':
                    LaunchConfiguration('debug_expected_imu_rate_hz'),
                'imu_qos_depth':
                    LaunchConfiguration('yesense_imu_qos_depth'),
                'raw_hw_qos_depth':
                    LaunchConfiguration('yesense_raw_hw_qos_depth'),
                'imu_qos_reliability':
                    LaunchConfiguration('yesense_imu_qos_reliability'),
                'raw_hw_qos_reliability':
                    LaunchConfiguration('yesense_raw_hw_qos_reliability'),
                'publish_queue_depth':
                    LaunchConfiguration('yesense_publish_queue_depth'),
                'ros_imu_publish_queue_depth':
                    LaunchConfiguration(
                        'yesense_ros_imu_publish_queue_depth'),
                'legacy_publish_queue_depth':
                    LaunchConfiguration(
                        'yesense_legacy_publish_queue_depth'),
                'realtime_thread_priority':
                    LaunchConfiguration(
                        'yesense_realtime_thread_priority'),
            }.items(),
        ),

        # ── Sync Node ────────────────────────────────────────────────
        # subscribes: /image_raw, /imu/data_raw, /imu/pipeline_ready
        # publishes:  /sync/image_raw, /sync/imu, /sync/imu_batch
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
                'enable_resampled_imu':
                    LaunchConfiguration('enable_resampled_imu'),
                'resampled_imu_topic':
                    LaunchConfiguration('resampled_imu_topic'),
                'resampled_imu_rate_hz':
                    LaunchConfiguration('resampled_imu_rate_hz'),
                'resampled_imu_latency_ms':
                    LaunchConfiguration('resampled_imu_latency_ms'),
                'resampled_imu_max_gap_ms':
                    LaunchConfiguration('resampled_imu_max_gap_ms'),
                'resampled_imu_threaded_publish':
                    LaunchConfiguration('resampled_imu_threaded_publish'),
                'publish_batch_imu':
                    LaunchConfiguration('publish_batch_imu'),
                'batch_imu_topic':
                    LaunchConfiguration('batch_imu_topic'),
                'enable_interpolation':
                    LaunchConfiguration('enable_interpolation'),
                'max_sync_wait_ms':
                    LaunchConfiguration('max_sync_wait_ms'),
                'max_interp_gap_ms':
                    LaunchConfiguration('max_interp_gap_ms'),
                'drop_frame_on_missing_imu':
                    LaunchConfiguration('drop_frame_on_missing_imu'),
                'warn_on_queue_backlog':
                    LaunchConfiguration('warn_on_queue_backlog'),
                'debug_enable':
                    LaunchConfiguration('debug_enable'),
                'debug_trace_samples':
                    LaunchConfiguration('debug_trace_samples'),
                'debug_expected_imu_rate_hz':
                    LaunchConfiguration('debug_expected_imu_rate_hz'),
                'executor_threads':
                    LaunchConfiguration('executor_threads'),
                # NEW state-machine params
                'camera_startup_drop_sec':
                    LaunchConfiguration('camera_startup_drop_sec'),
                'sync_wait_imu_ready_min_samples':
                    LaunchConfiguration(
                        'sync_wait_imu_ready_min_samples'),
                'sync_wait_imu_ready_min_span_ms':
                    LaunchConfiguration(
                        'sync_wait_imu_ready_min_span_ms'),
                'sync_wait_imu_ready_max_std_ms':
                    LaunchConfiguration(
                        'sync_wait_imu_ready_max_std_ms'),
                'first_sync_safety_margin_ms':
                    LaunchConfiguration('first_sync_safety_margin_ms'),
                'sync_fail_lag_threshold_ms':
                    LaunchConfiguration('sync_fail_lag_threshold_ms'),
                'sync_fail_consecutive_limit':
                    LaunchConfiguration('sync_fail_consecutive_limit'),
                'imu_pipeline_ready_topic':
                    LaunchConfiguration('imu_pipeline_ready_topic'),
                # NEW: steady-domain params
                'steady_cam_to_imu_offset_sec':
                    LaunchConfiguration(
                        'steady_cam_to_imu_offset_sec'),
                'first_sync_timeout_sec':
                    LaunchConfiguration('first_sync_timeout_sec'),
                'first_sync_drop_limit':
                    LaunchConfiguration('first_sync_drop_limit'),
                # Phase 1A params
                'deterministic_sync':
                    LaunchConfiguration('deterministic_sync'),
                'imu_raw_hw_topic':
                    LaunchConfiguration('imu_raw_hw_topic'),
                'raw_hw_qos_depth':
                    LaunchConfiguration('raw_hw_qos_depth'),
                'raw_hw_qos_reliability':
                    LaunchConfiguration('raw_hw_qos_reliability'),
                'legacy_imu_qos_depth':
                    LaunchConfiguration('legacy_imu_qos_depth'),
                'enable_header_rewrite':
                    LaunchConfiguration('enable_header_rewrite'),
                'min_stable_cam_frames':
                    LaunchConfiguration('min_stable_cam_frames'),
                'cam_stable_max_std_ms':
                    LaunchConfiguration('cam_stable_max_std_ms'),
            }],
        ),
    ])
