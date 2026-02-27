cmake_minimum_required(VERSION 3.14)
project(orbslam3_vendor)

find_package(ament_cmake REQUIRED)
find_package(OpenCV REQUIRED)
find_package(Eigen3 REQUIRED)

include(ExternalProject)

set(ORBSLAM3_SOURCE_DIR ${CMAKE_CURRENT_BINARY_DIR}/orbslam3-src)
set(ORBSLAM3_BUILD_DIR ${CMAKE_CURRENT_BINARY_DIR}/orbslam3-build)
set(ORBSLAM3_INSTALL_DIR ${CMAKE_INSTALL_PREFIX})

# Patch file for C++17 / OpenCV 4.x compatibility
set(PATCH_DIR ${CMAKE_CURRENT_SOURCE_DIR}/patches)

ExternalProject_Add(orbslam3_external
  GIT_REPOSITORY https://github.com/UZ-SLAMLab/ORB_SLAM3.git
  GIT_TAG v1.0-release
  GIT_SHALLOW TRUE
  SOURCE_DIR ${ORBSLAM3_SOURCE_DIR}
  BINARY_DIR ${ORBSLAM3_BUILD_DIR}

  # Apply patches after download
  PATCH_COMMAND
    ${CMAKE_COMMAND} -E copy ${PATCH_DIR}/CMakeLists.txt.patch ${ORBSLAM3_SOURCE_DIR}/CMakeLists.txt.patch &&
    cd ${ORBSLAM3_SOURCE_DIR} && git checkout -- . &&
    patch -p1 < ${PATCH_DIR}/orbslam3_cpp17_opencv4.patch || true

  CMAKE_ARGS
    -DCMAKE_BUILD_TYPE=Release
    -DCMAKE_CXX_STANDARD=17
    -DCMAKE_INSTALL_PREFIX=${ORBSLAM3_INSTALL_DIR}
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON
    -DOpenCV_DIR=${OpenCV_DIR}
    -DEIGEN3_INCLUDE_DIR=${EIGEN3_INCLUDE_DIR}

  BUILD_COMMAND ${CMAKE_COMMAND} --build . --config Release -- -j4
  INSTALL_COMMAND ""  # We handle install ourselves below

  BUILD_BYPRODUCTS
    ${ORBSLAM3_SOURCE_DIR}/lib/libORB_SLAM3.so
    ${ORBSLAM3_SOURCE_DIR}/Thirdparty/DBoW2/lib/libDBoW2.so
    ${ORBSLAM3_SOURCE_DIR}/Thirdparty/g2o/lib/libg2o.so
)

# Download ORB vocabulary
set(VOCAB_URL "https://github.com/UZ-SLAMLab/ORB_SLAM3/raw/master/Vocabulary/ORBvoc.txt.tar.gz")
set(VOCAB_DIR ${CMAKE_CURRENT_BINARY_DIR}/vocabulary)
set(VOCAB_FILE ${VOCAB_DIR}/ORBvoc.txt)

ExternalProject_Add(orbvoc_download
  URL ${VOCAB_URL}
  SOURCE_DIR ${VOCAB_DIR}
  CONFIGURE_COMMAND ""
  BUILD_COMMAND ""
  INSTALL_COMMAND ""
  DOWNLOAD_NO_EXTRACT FALSE
)

# Install libraries
install(FILES
  ${ORBSLAM3_SOURCE_DIR}/lib/libORB_SLAM3.so
  DESTINATION lib
)
install(FILES
  ${ORBSLAM3_SOURCE_DIR}/Thirdparty/DBoW2/lib/libDBoW2.so
  DESTINATION lib
)
install(FILES
  ${ORBSLAM3_SOURCE_DIR}/Thirdparty/g2o/lib/libg2o.so
  DESTINATION lib
)

# Install headers
install(DIRECTORY ${ORBSLAM3_SOURCE_DIR}/include/
  DESTINATION include/orbslam3
)
install(DIRECTORY ${ORBSLAM3_SOURCE_DIR}/Thirdparty/DBoW2/DBoW2/
  DESTINATION include/orbslam3/Thirdparty/DBoW2/DBoW2
  FILES_MATCHING PATTERN "*.h"
)
install(DIRECTORY ${ORBSLAM3_SOURCE_DIR}/Thirdparty/g2o/g2o/
  DESTINATION include/orbslam3/Thirdparty/g2o/g2o
  FILES_MATCHING PATTERN "*.h"
)
install(DIRECTORY ${ORBSLAM3_SOURCE_DIR}/Thirdparty/Sophus/sophus/
  DESTINATION include/orbslam3/Thirdparty/Sophus/sophus
  FILES_MATCHING PATTERN "*.hpp"
)

# Install vocabulary
install(FILES ${VOCAB_FILE}
  DESTINATION share/${PROJECT_NAME}/vocabulary
  OPTIONAL  # May not exist if download fails
)

# Export cmake config for downstream packages
install(DIRECTORY ${ORBSLAM3_SOURCE_DIR}/
  DESTINATION share/${PROJECT_NAME}/orbslam3_source
  FILES_MATCHING
    PATTERN "*.h"
    PATTERN "*.hpp"
    PATTERN "build" EXCLUDE
    PATTERN ".git" EXCLUDE
)

# Create cmake config file for downstream
file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/orbslam3_vendorConfig.cmake
"# orbslam3_vendor CMake config
set(ORBSLAM3_INCLUDE_DIRS
  \${orbslam3_vendor_DIR}/../../../include/orbslam3
  \${orbslam3_vendor_DIR}/../../../include/orbslam3/Thirdparty/DBoW2
  \${orbslam3_vendor_DIR}/../../../include/orbslam3/Thirdparty/g2o
  \${orbslam3_vendor_DIR}/../../../include/orbslam3/Thirdparty/Sophus
)
set(ORBSLAM3_LIBRARIES
  \${orbslam3_vendor_DIR}/../../../lib/libORB_SLAM3.so
  \${orbslam3_vendor_DIR}/../../../lib/libDBoW2.so
  \${orbslam3_vendor_DIR}/../../../lib/libg2o.so
)
set(ORBSLAM3_VOCABULARY
  \${orbslam3_vendor_DIR}/../../../share/orbslam3_vendor/vocabulary/ORBvoc.txt
)
")

install(FILES ${CMAKE_CURRENT_BINARY_DIR}/orbslam3_vendorConfig.cmake
  DESTINATION share/${PROJECT_NAME}/cmake
)

ament_package()
