#!/usr/bin/env bash
set -euo pipefail

# 读取你这份配置（按你给的实际路径）
export SEARXNG_SETTINGS_PATH="/home/v-huzhengyu/searxng-conf/settings.yml"

# —— 访问范围 ——
# 仅本机使用（推荐）：HOST=127.0.0.1
# 如果确实要临时对外（例如同网段其他机器访问），再改成 0.0.0.0
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8888}"

# 启动（只用你验证过的参数组合）
exec granian --interface wsgi --host "${HOST}" --port "${PORT}" searx.webapp:app