#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/cpp"

mkdir -p build
cd build

echo "==> Configuring CMake ..."
PYBIND11_DIR=$(python3 -c "import pybind11; print(pybind11.get_cmake_dir())")
cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$PYBIND11_DIR" "$@"

echo "==> Building ..."
make -j"$(nproc)"

echo "==> Done. Module ready at: cpp/build/physics_engine*.so"
