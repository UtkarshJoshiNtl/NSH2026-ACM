#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/cpp"

mkdir -p build
cd build

echo "==> Configuring CMake ..."
cmake .. -DCMAKE_BUILD_TYPE=Release "$@"

echo "==> Building ..."
make -j"$(nproc)"

echo "==> Done. Module ready at: cpp/build/physics_engine*.so"
