#!/usr/bin/env bash
# run_steady_experiment.sh — 运行 3 次 cam_imu_sync 实验，每次 ~20 秒
# 使用 docker exec 在 autoware_env_v2_host 容器内执行
set -euo pipefail

CONTAINER="autoware_env_v2_host"
LOG_DIR="/home/gxxl/slam_ws_v2/extra_ws/logs/cam_imu_sync"
DURATION_SEC=20
NUM_RUNS=3

for i in $(seq 1 $NUM_RUNS); do
    RUN_ID="steady_exp_$(printf '%02d' $i)"
    echo ""
    echo "========================================================"
    echo "  RUN $i / $NUM_RUNS — run_id=$RUN_ID  (${DURATION_SEC}s)"
    echo "========================================================"
    echo ""

    # 启动 launch 并在 DURATION_SEC 后 SIGINT
    docker exec "$CONTAINER" bash -c "
        source /opt/ros/humble/setup.bash
        source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash
        timeout --signal=INT ${DURATION_SEC} \
            ros2 launch cam_imu_sync cam_imu_sync.launch.py run_id:=${RUN_ID} \
            2>&1 || true
    "

    echo ""
    echo "  ✓ Run $i finished. Waiting 3s before next run..."
    sleep 3
done

echo ""
echo "========================================================"
echo "  All $NUM_RUNS runs complete. Logs in $LOG_DIR"
echo "========================================================"
ls -la "$LOG_DIR" | grep steady_exp
