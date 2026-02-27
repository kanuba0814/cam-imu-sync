#ifndef ORBSLAM3_ROS2__ORBSLAM3_NODE_HPP_
#define ORBSLAM3_ROS2__ORBSLAM3_NODE_HPP_

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/imu.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <std_msgs/msg/int32.hpp>
#include <cv_bridge/cv_bridge.h>

#include <System.h>

#include <deque>
#include <mutex>
#include <memory>

namespace orbslam3_ros2
{

class OrbSlam3Node : public rclcpp::Node
{
public:
  explicit OrbSlam3Node(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());
  ~OrbSlam3Node();

private:
  void image_callback(const sensor_msgs::msg::Image::ConstSharedPtr & msg);
  void imu_callback(const sensor_msgs::msg::Imu::ConstSharedPtr & msg);

  // Convert ORB-SLAM3 pose (Sophus::SE3f) to PoseStamped
  geometry_msgs::msg::PoseStamped se3_to_pose_stamped(
    const Sophus::SE3f & Tcw, const rclcpp::Time & stamp);

  // Publish map points for visualization
  void publish_map_points();

  // ORB-SLAM3 system
  std::unique_ptr<ORB_SLAM3::System> slam_system_;

  // Subscribers
  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr image_sub_;
  rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr imu_sub_;

  // Publishers
  rclcpp::Publisher<geometry_msgs::msg::PoseStamped>::SharedPtr pose_pub_;
  rclcpp::Publisher<std_msgs::msg::Int32>::SharedPtr tracking_state_pub_;
  rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr map_points_pub_;

  // IMU buffer
  std::deque<ORB_SLAM3::IMU::Point> imu_buffer_;
  std::mutex imu_mutex_;

  // Parameters
  std::string vocabulary_path_;
  std::string settings_path_;
  double last_image_timestamp_;

  // Timer for map points publishing
  rclcpp::TimerBase::SharedPtr map_points_timer_;
};

}  // namespace orbslam3_ros2

#endif  // ORBSLAM3_ROS2__ORBSLAM3_NODE_HPP_
