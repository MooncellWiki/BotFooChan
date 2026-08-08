#!/usr/bin/env sh
# 从 uv.lock 读出锁定的 playwright 版本。
# 这是 sidecar 镜像版本的唯一来源，CI 与本地构建都调它。
set -e

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
LOCK="$ROOT/uv.lock"

VERSION=$(awk '/^name = "playwright"$/{f=1; next} f && /^version = /{gsub(/"/,"",$3); print $3; exit}' "$LOCK")

if [ -z "$VERSION" ]; then
  echo "无法从 $LOCK 解析 playwright 版本" >&2
  exit 1
fi

echo "$VERSION"
