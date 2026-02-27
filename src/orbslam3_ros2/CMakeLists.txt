cmake_minimum_required(VERSION 3.14)
project(orbslam3_ros2)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(image_transport REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(OpenCV REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(orbslam3_vendor REQUIRED)

add_executable(orbslam3_mono_inertial_node
  src/orbslam3_node.cpp
)

target_include_directories(orbslam3_mono_inertial_node PRIVATE
  include
  ${ORBSLAM3_INCLUDE_DIRS}
  ${EIGEN3_INCLUDE_DIR}
  ${OpenCV_INCLUDE_DIRS}
)

target_link_libraries(orbslam3_mono_inertial_node
  ${ORBSLAM3_LIBRARIES}
  ${OpenCV_LIBRARIES}
)

ament_target_dependencies(orbslam3_mono_inertial_node
  rclcpp
  sensor_msgs
  geometry_msgs
  std_msgs
  cv_bridge
  image_transport
  tf2
  tf2_ros
  tf2_geometry_msgs
)

install(TARGETS
  orbslam3_mono_inertial_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config
)

install(DIRECTORY include/
  DESTINATION include
)

ament_package()
