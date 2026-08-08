#!/usr/bin/env sh
# 本地构建 Playwright Server sidecar，版本自动取自 uv.lock。
# 用法: ./docker/playwright/build.sh [额外的 docker build 参数...]
set -e

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VERSION=$("$HERE/version.sh")

echo "Building playwright sidecar v$VERSION"

exec docker build \
  --build-arg "PLAYWRIGHT_VERSION=$VERSION" \
  -t "starheart/botfoochan-playwright:$VERSION" \
  -t "starheart/botfoochan-playwright:latest" \
  "$@" \
  "$HERE"
