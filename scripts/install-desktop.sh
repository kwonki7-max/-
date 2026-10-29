#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/install.sh
# Keep caches inside the writable cloud workspace without changing HOME.
export npm_config_cache="${npm_config_cache:-/workspace/.npm-cache}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/workspace/.cache}"
export electron_config_cache="${electron_config_cache:-/workspace/.electron-cache}"
export ELECTRON_BUILDER_CACHE="${ELECTRON_BUILDER_CACHE:-/workspace/.electron-builder-cache}"
# Node 24 fetch must use the platform's configured egress proxy.
export NODE_USE_ENV_PROXY=1
npm ci --ignore-scripts
node node_modules/electron/install.js
npm run test:desktop
