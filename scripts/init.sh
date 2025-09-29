#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
SPLIT_DIR="$REPO_ROOT/tools/split"

handle_error() {
    local exit_code=$?
    local line_number=$1
    echo "[ERROR] Script failed at line $line_number with exit code $exit_code"
    echo "[ERROR] Initialization incomplete. Please check the logs and try again."
    exit $exit_code
}

trap 'handle_error $LINENO' ERR

echo "[INFO] Creating logs directory at $REPO_ROOT/logs..."
if mkdir -p "$REPO_ROOT/logs"; then
    echo "[INFO] logs directory created or already exists."
else
    echo "[ERROR] Failed to create logs directory."
    exit 1
fi

echo "[INFO] Initializing SPLiT submodule..."
if ! git submodule update --init --recursive; then
    echo "[ERROR] Failed to initialize git submodules. Check your git configuration and network connection."
    exit 1
fi

echo "[INFO] Checking if SPLiT directory exists..."
if [ ! -d "$SPLIT_DIR" ]; then
    echo "[ERROR] SPLiT directory $SPLIT_DIR does not exist after submodule initialization."
    exit 1
fi

echo "[INFO] Entering $SPLIT_DIR..."
cd "$SPLIT_DIR"

echo "[INFO] Creating SPLiT build directory..."
if ! mkdir -p build; then
    echo "[ERROR] Failed to create build directory in $SPLIT_DIR"
    exit 1
fi

echo "[INFO] Installing SPLiT dependencies..."
echo "[INFO] Updating package lists..."
if ! sudo apt update; then
    echo "[ERROR] Failed to update package lists. Check your internet connection and repository configuration."
    exit 1
fi

echo "[INFO] Installing build tools..."
if ! sudo apt install -y build-essential cmake gnuplot; then
    echo "[ERROR] Failed to install basic build tools."
    exit 1
fi

echo "[INFO] Installing Boost libraries and graphviz..."
if ! sudo apt install -y libboost-all-dev graphviz; then
    echo "[ERROR] Failed to install Boost libraries or graphviz."
    exit 1
fi

echo "[INFO] Installing YAML and logging libraries..."
if ! sudo apt install -y libyaml-cpp-dev; then
    echo "[ERROR] Failed to install YAML C++ library."
    exit 1
fi

if ! sudo apt install -y libspdlog-dev; then
    echo "[ERROR] Failed to install spdlog library."
    exit 1
fi

echo "[INFO] Running cmake configuration..."
cd build
if ! cmake ..; then
    echo "[ERROR] CMake configuration failed. Check if all dependencies are properly installed."
    exit 1
fi

echo "[INFO] Building SPLiT project..."
if ! make; then
    echo "[ERROR] SPLiT build failed. Check the compilation output above for details."
    exit 1
fi

echo "[INFO] Building sort binary..."
cd "$REPO_ROOT"

if [ ! -f "Makefile" ]; then
    echo "[ERROR] Makefile not found in $REPO_ROOT. Cannot build sort binary."
    exit 1
fi

if ! make; then
    echo "[ERROR] Failed to build sort binary. Check the compilation output above for details."
    exit 1
fi

echo "[SUCCESS] Initialization completed successfully!"
echo "[INFO] You can now run the sorting algorithms using: ./build/sort <mode> <algorithm> [options] from the repository root."