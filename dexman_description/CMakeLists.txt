cmake_minimum_required(VERSION 3.8)

project(dexman_description)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY
    launch
    rviz
    config
    meshes
    robots
  DESTINATION
    share/${PROJECT_NAME}
)

ament_package()
