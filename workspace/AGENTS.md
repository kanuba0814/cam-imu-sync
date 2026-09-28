# Repository Guidelines

## Project Structure & Module Organization
This workspace is a multi-repo SLAM/simulation environment, not a single package:
- `autoware/`: ROS 2 meta-repository (uses `repositories/autoware.repos` and `src/` imports).
- `extra_ws/src/ORB_SLAM3_ROS2/`: custom ROS 2 package (`src/`, `launch/`, `config/`, `camera_calibration/`).
- `carla/`: CARLA simulator runtime and plugins.
- `libs/`: third-party libraries (for example `ORB_SLAM3`, `Pangolin`).
- `autoware-contents/`: maps and large data assets.

Keep generated artifacts out of commits (`build/`, `install/`, `log/`, recorded bags, generated maps).

## Build, Test, and Development Commands
Use commands from the subproject you are changing:
- For ROS packages in this workspace, build, test, and run validation inside the `autoware_env_v2_host` container. The host ROS environment is not the active development environment; ROS and required libraries live in that container.
- Import Autoware sources: `cd autoware && vcs import src < repositories/autoware.repos`
- Build Autoware: `cd autoware && colcon build --mixin debug compile-commands`
- Run Autoware checks: `cd autoware && pre-commit run -a`
- Build ORB_SLAM3 library: `cd extra_ws/src/ORB_SLAM3_ROS2/ORB_SLAM3 && ./build.sh`
- Build ORB ROS 2 package: `cd extra_ws && colcon build --packages-select orb_slam3_ros2`
- Test ORB package: `cd extra_ws && colcon test --packages-select orb_slam3_ros2 && colcon test-result --verbose`
- Run CARLA server: `cd carla && ./CarlaUE4.sh`

## Coding Style & Naming Conventions
- C++: run `clang-format` using the nearest `.clang-format` file.
- Python in `autoware/`: Black + isort + flake8 (`max-line-length = 100`, isort profile `black`).
- ROS node and target names should stay snake_case (for example `imu_mono_node_cpp`, `orb_camera_info_node`).
- Prefer descriptive launch/config names matching behavior (`mapping.launch.py`, `pointmatcher_config.yaml`).

## Testing Guidelines
- Minimum for ROS 2 changes: containerized `colcon build` + `colcon test` on affected packages in `autoware_env_v2_host`.
- In `extra_ws/src/ORB_SLAM3_ROS2`, `ament_lint_auto` is enabled when `BUILD_TESTING=ON`; treat lint failures as blocking.
- For simulation features, include runtime validation steps (launch command, expected topics/TF, and RViz/CARLA output).

## Commit & Pull Request Guidelines
- Commit inside the correct nested repo (`git -C autoware ...`, `git -C extra_ws/src/ORB_SLAM3_ROS2 ...`).
- `autoware/` follows Conventional Commits (`feat(scope): ...`, `fix(scope): ...`, `chore: ...`).
- Keep commits focused (one functional change per commit) and reference issue IDs when available.
- PRs should include: purpose, changed paths, validation commands run, and screenshots/log snippets for UI or visualization changes.
