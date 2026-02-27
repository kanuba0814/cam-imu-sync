#include "orbslam3_ros2/orbslam3_node.hpp"

#include <opencv2/imgproc.hpp>
#include <sensor_msgs/msg/point_field.hpp>

#include <chrono>
#include <vector>

namespace orbslam3_ros2
{

OrbSlam3Node::OrbSlam3Node(const rclcpp::NodeOptions & options)
: Node("orbslam3_mono_inertial_node", options),
  last_image_timestamp_(0.0)
{
  // Declare parameters
  this->declare_parameter<std::string>("vocabulary_path", "");
  this->declare_parameter<std::string>("settings_path", "");
  this->declare_parameter<std::string>("image_topic", "/sensing/camera/CAM_FRONT/image_raw");
  this->declare_parameter<std::string>("imu_topic", "/sensing/imu/tamagawa/imu_raw");
  this->declare_parameter<bool>("publish_map_points", true);
  this->declare_parameter<double>("map_points_publish_rate", 1.0);

  vocabulary_path_ = this->get_parameter("vocabulary_path").as_string();
  settings_path_ = this->get_parameter("settings_path").as_string();

  if (vocabulary_path_.empty() || settings_path_.empty()) {
    RCLCPP_FATAL(
      this->get_logger(),
      "vocabulary_path and settings_path must be set!");
    throw std::runtime_error("Missing required parameters");
  }

  RCLCPP_INFO(this->get_logger(), "Initializing ORB-SLAM3...");
  RCLCPP_INFO(this->get_logger(), "  Vocabulary: %s", vocabulary_path_.c_str());
  RCLCPP_INFO(this->get_logger(), "  Settings: %s", settings_path_.c_str());

  // Create ORB-SLAM3 system in Mono-Inertial mode, no viewer
  slam_system_ = std::make_unique<ORB_SLAM3::System>(
    vocabulary_path_,
    settings_path_,
    ORB_SLAM3::System::IMU_MONOCULAR,
    false  // useViewer = false
  );

  RCLCPP_INFO(this->get_logger(), "ORB-SLAM3 initialized successfully");

  // Publishers
  pose_pub_ = this->create_publisher<geometry_msgs::msg::PoseStamped>(
    "/orbslam3/camera_pose", 10);
  tracking_state_pub_ = this->create_publisher<std_msgs::msg::Int32>(
    "/orbslam3/tracking_state", 10);
  map_points_pub_ = this->create_publisher<sensor_msgs::msg::PointCloud2>(
    "/orbslam3/map_points", 10);

  // Subscribers
  auto image_topic = this->get_parameter("image_topic").as_string();
  auto imu_topic = this->get_parameter("imu_topic").as_string();

  // IMU subscriber with high queue to avoid dropping messages
  imu_sub_ = this->create_subscription<sensor_msgs::msg::Imu>(
    imu_topic, rclcpp::SensorDataQoS().keep_last(200),
    std::bind(&OrbSlam3Node::imu_callback, this, std::placeholders::_1));

  // Image subscriber
  image_sub_ = this->create_subscription<sensor_msgs::msg::Image>(
    image_topic, rclcpp::SensorDataQoS().keep_last(5),
    std::bind(&OrbSlam3Node::image_callback, this, std::placeholders::_1));

  // Optional map points publishing timer
  if (this->get_parameter("publish_map_points").as_bool()) {
    double rate = this->get_parameter("map_points_publish_rate").as_double();
    auto period = std::chrono::duration<double>(1.0 / rate);
    map_points_timer_ = this->create_wall_timer(
      std::chrono::duration_cast<std::chrono::nanoseconds>(period),
      std::bind(&OrbSlam3Node::publish_map_points, this));
  }

  RCLCPP_INFO(
    this->get_logger(), "Subscribing to image: %s, imu: %s",
    image_topic.c_str(), imu_topic.c_str());
}

OrbSlam3Node::~OrbSlam3Node()
{
  if (slam_system_) {
    slam_system_->Shutdown();
  }
}

void OrbSlam3Node::imu_callback(const sensor_msgs::msg::Imu::ConstSharedPtr & msg)
{
  std::lock_guard<std::mutex> lock(imu_mutex_);

  double timestamp = rclcpp::Time(msg->header.stamp).seconds();

  // ORB-SLAM3 IMU::Point: (acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, timestamp)
  ORB_SLAM3::IMU::Point imu_point(
    static_cast<float>(msg->linear_acceleration.x),
    static_cast<float>(msg->linear_acceleration.y),
    static_cast<float>(msg->linear_acceleration.z),
    static_cast<float>(msg->angular_velocity.x),
    static_cast<float>(msg->angular_velocity.y),
    static_cast<float>(msg->angular_velocity.z),
    timestamp);

  imu_buffer_.push_back(imu_point);

  // Keep buffer bounded (max ~5 seconds at 50Hz = 250 samples)
  while (imu_buffer_.size() > 300) {
    imu_buffer_.pop_front();
  }
}

void OrbSlam3Node::image_callback(const sensor_msgs::msg::Image::ConstSharedPtr & msg)
{
  double timestamp = rclcpp::Time(msg->header.stamp).seconds();

  // Convert image to grayscale
  cv::Mat gray;
  try {
    cv_bridge::CvImageConstPtr cv_ptr;
    if (msg->encoding == "bgra8") {
      cv_ptr = cv_bridge::toCvShare(msg, "bgra8");
      cv::cvtColor(cv_ptr->image, gray, cv::COLOR_BGRA2GRAY);
    } else if (msg->encoding == "bgr8") {
      cv_ptr = cv_bridge::toCvShare(msg, "bgr8");
      cv::cvtColor(cv_ptr->image, gray, cv::COLOR_BGR2GRAY);
    } else if (msg->encoding == "rgb8") {
      cv_ptr = cv_bridge::toCvShare(msg, "rgb8");
      cv::cvtColor(cv_ptr->image, gray, cv::COLOR_RGB2GRAY);
    } else if (msg->encoding == "mono8") {
      cv_ptr = cv_bridge::toCvShare(msg, "mono8");
      gray = cv_ptr->image.clone();
    } else {
      // Try generic conversion
      cv_ptr = cv_bridge::toCvShare(msg);
      if (cv_ptr->image.channels() > 1) {
        cv::cvtColor(cv_ptr->image, gray, cv::COLOR_BGR2GRAY);
      } else {
        gray = cv_ptr->image.clone();
      }
    }
  } catch (const cv_bridge::Exception & e) {
    RCLCPP_ERROR(this->get_logger(), "cv_bridge exception: %s", e.what());
    return;
  }

  // Extract IMU measurements between last image and current image
  std::vector<ORB_SLAM3::IMU::Point> imu_measurements;
  {
    std::lock_guard<std::mutex> lock(imu_mutex_);
    for (const auto & imu_point : imu_buffer_) {
      if (imu_point.t > last_image_timestamp_ && imu_point.t <= timestamp) {
        imu_measurements.push_back(imu_point);
      }
    }
    // Remove old IMU data (before previous image timestamp)
    while (!imu_buffer_.empty() && imu_buffer_.front().t < last_image_timestamp_) {
      imu_buffer_.pop_front();
    }
  }

  last_image_timestamp_ = timestamp;

  if (imu_measurements.empty()) {
    RCLCPP_WARN_THROTTLE(
      this->get_logger(), *this->get_clock(), 2000,
      "No IMU measurements between frames, skipping");
    return;
  }

  // Track with ORB-SLAM3
  Sophus::SE3f Tcw = slam_system_->TrackMonocular(gray, timestamp, imu_measurements);

  // Get tracking state
  int tracking_state = static_cast<int>(slam_system_->GetTrackingState());

  // Publish tracking state
  auto state_msg = std::make_unique<std_msgs::msg::Int32>();
  state_msg->data = tracking_state;
  tracking_state_pub_->publish(std::move(state_msg));

  // Only publish pose if tracking is OK (state == 2)
  if (tracking_state == 2) {
    // ORB-SLAM3 returns Tcw (camera pose in world frame)
    // We need Twc (world-to-camera, i.e., camera position in world)
    Sophus::SE3f Twc = Tcw.inverse();
    auto pose_msg = se3_to_pose_stamped(Twc, msg->header.stamp);
    pose_pub_->publish(pose_msg);
  }
}

geometry_msgs::msg::PoseStamped OrbSlam3Node::se3_to_pose_stamped(
  const Sophus::SE3f & Twc, const rclcpp::Time & stamp)
{
  geometry_msgs::msg::PoseStamped pose_msg;
  pose_msg.header.stamp = stamp;
  pose_msg.header.frame_id = "orbslam3_world";

  // Extract translation
  Eigen::Vector3f t = Twc.translation();
  pose_msg.pose.position.x = static_cast<double>(t.x());
  pose_msg.pose.position.y = static_cast<double>(t.y());
  pose_msg.pose.position.z = static_cast<double>(t.z());

  // Extract quaternion
  Eigen::Quaternionf q = Twc.unit_quaternion();
  pose_msg.pose.orientation.x = static_cast<double>(q.x());
  pose_msg.pose.orientation.y = static_cast<double>(q.y());
  pose_msg.pose.orientation.z = static_cast<double>(q.z());
  pose_msg.pose.orientation.w = static_cast<double>(q.w());

  return pose_msg;
}

void OrbSlam3Node::publish_map_points()
{
  if (!slam_system_) return;

  auto all_map_points = slam_system_->GetTrackedMapPoints();
  if (all_map_points.empty()) return;

  // Build PointCloud2 message
  sensor_msgs::msg::PointCloud2 cloud_msg;
  cloud_msg.header.stamp = this->now();
  cloud_msg.header.frame_id = "orbslam3_world";

  // Count valid points
  std::vector<Eigen::Vector3f> valid_points;
  for (auto * mp : all_map_points) {
    if (mp && !mp->isBad()) {
      Eigen::Vector3f pos = mp->GetWorldPos();
      valid_points.push_back(pos);
    }
  }

  if (valid_points.empty()) return;

  cloud_msg.height = 1;
  cloud_msg.width = static_cast<uint32_t>(valid_points.size());
  cloud_msg.is_dense = true;
  cloud_msg.is_bigendian = false;

  sensor_msgs::msg::PointField field_x, field_y, field_z;
  field_x.name = "x";
  field_x.offset = 0;
  field_x.datatype = sensor_msgs::msg::PointField::FLOAT32;
  field_x.count = 1;
  field_y.name = "y";
  field_y.offset = 4;
  field_y.datatype = sensor_msgs::msg::PointField::FLOAT32;
  field_y.count = 1;
  field_z.name = "z";
  field_z.offset = 8;
  field_z.datatype = sensor_msgs::msg::PointField::FLOAT32;
  field_z.count = 1;
  cloud_msg.fields = {field_x, field_y, field_z};
  cloud_msg.point_step = 12;  // 3 * sizeof(float)
  cloud_msg.row_step = cloud_msg.point_step * cloud_msg.width;

  cloud_msg.data.resize(cloud_msg.row_step);
  for (size_t i = 0; i < valid_points.size(); ++i) {
    float x = valid_points[i].x();
    float y = valid_points[i].y();
    float z = valid_points[i].z();
    memcpy(&cloud_msg.data[i * 12], &x, 4);
    memcpy(&cloud_msg.data[i * 12 + 4], &y, 4);
    memcpy(&cloud_msg.data[i * 12 + 8], &z, 4);
  }

  map_points_pub_->publish(cloud_msg);
}

}  // namespace orbslam3_ros2

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<orbslam3_ros2::OrbSlam3Node>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
