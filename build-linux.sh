#!/usr/bin/env bash
set -euo pipefail
project_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$project_dir"
zig_bin="${ZIG:-zig}"
if ! command -v "$zig_bin" >/dev/null 2>&1; then
    echo '找不到 Zig。请安装 Zig 0.14.1，或使用 ZIG=/完整路径/zig ./build-linux.sh。' >&2
    exit 1
fi
if [[ "$("$zig_bin" version)" != '0.14.1' ]]; then
    echo '本工程使用 Zig 0.14.1，请使用匹配版本。' >&2
    exit 1
fi
mkdir -p linux/.build-cache/local linux/.build-cache/global
node 正式版/tools/gen_atlas.js
cache_args=(--cache-dir linux/.build-cache/local --global-cache-dir linux/.build-cache/global)
target_args=(-target "${COMPLEXWEEPER_TARGET:-x86_64-linux-gnu}" -mcpu baseline)
"$zig_bin" build-lib 正式版/src/linux_api.zig --name complexweeper -dynamic -O ReleaseSafe -fstrip \
    "${target_args[@]}" \
    "${cache_args[@]}" -femit-bin=linux/libcomplexweeper.so
"$zig_bin" build-exe 正式版/src/test_linux.zig -O ReleaseSafe -fstrip \
    "${target_args[@]}" \
    "${cache_args[@]}" -femit-bin=linux/rules-selftest
python3 linux/prepare_assets.py
./complexweeper --selftest
echo '构建与自检通过。运行 ./complexweeper 即可开始。'
