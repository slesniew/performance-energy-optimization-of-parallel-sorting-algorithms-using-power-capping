#!/bin/bash

DEFAULT_POWER_LIMIT=125
POWER_CAP_PATH="/sys/class/powercap/intel-rapl/intel-rapl:0/constraint_0_power_limit_uw"
DOCKER_IMAGE_NAME="sort-app:latest"
DOCKER_APP_LOGS_PATH="/app/logs"
SSH_USER="s184711"
SSH_HOST="kask.eti.pg.gda.pl"
SSH_LOGS_PATH="/home/macierz/s184711/logs"
LOCAL_LOGS_DIR="logs"

set_power_limit() {
    local watts=${1:-$DEFAULT_POWER_LIMIT}
    local microwatts=$((watts * 1000000))
    echo "Setting power limit to ${watts}W"
    echo $microwatts > $POWER_CAP_PATH
}

check_power_limit() {
    local microwatts=$(cat $POWER_CAP_PATH)
    local watts=$((microwatts / 1000000))
    echo "Current power limit: ${watts}W"
}

copy_docker_logs() {
    local container_id=$1
    local log_dir=$2
    docker cp ${container_id}:${DOCKER_APP_LOGS_PATH}/${log_dir} ${LOCAL_LOGS_DIR}/
}

copy_ssh_logs() {
    local log_dir=$1
    scp -r ${SSH_USER}@${SSH_HOST}:${SSH_LOGS_PATH}/${log_dir} ${LOCAL_LOGS_DIR}/
}

build_sort_app_no_cache() {
    echo "Building ${DOCKER_IMAGE_NAME} with no cache..."
    docker build --no-cache -t $DOCKER_IMAGE_NAME .
}

clean_sort_app() {
    echo "Pruning all containers..."
    docker container prune -f
    
    echo "Removing ${DOCKER_IMAGE_NAME} image..."
    docker rmi $DOCKER_IMAGE_NAME 2>/dev/null || echo "Image ${DOCKER_IMAGE_NAME} not found"
}

show_help() {
    echo "=== Experiment Commands Help ==="
    echo ""
    echo "  set_power_limit [watts]     - Set power limit (default: ${DEFAULT_POWER_LIMIT}W)"
    echo "  check_power_limit           - Show current power limit"
    echo ""
    echo "  copy_docker_logs <container_id> <log_dir>  - Copy logs from Docker container"
    echo "  copy_ssh_logs <log_dir>                    - Copy logs from remote SSH server"
    echo ""
    echo "  build_sort_app_no_cache      - Build Docker image without cache"
    echo "  clean_sort_app               - Clean Docker image"
    echo ""
    echo "  show_help                    - Show this help message"
    echo ""
    echo "================================="
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    show_help
fi