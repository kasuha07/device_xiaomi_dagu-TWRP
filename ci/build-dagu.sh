#!/usr/bin/env bash
set -eo pipefail

build_root=${1:?Usage: build-dagu.sh BUILD_ROOT}
export ALLOW_MISSING_DEPENDENCIES=true
export BUILD_BROKEN_USES_NETWORK=true
export LC_ALL=C
export USE_CCACHE=1
export CCACHE_EXEC=/usr/bin/ccache
export CCACHE_DIR=${CCACHE_DIR:-"$build_root/.ccache"}
export CCACHE_MAXSIZE=8G

cd "$build_root"
ccache --max-size "$CCACHE_MAXSIZE"
# Android's environment setup reads variables that may be unset.
# shellcheck disable=SC1091
source build/envsetup.sh
lunch twrp_dagu-eng
mka adbd bootimage -j"${BUILD_JOBS:-$(nproc)}"
ccache --show-stats
