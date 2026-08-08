# syntax=docker/dockerfile:1

# Playwright Server sidecar：浏览器进程从 bot 镜像里剥离出来，通过 WS 远程通信。
#
# 版本的唯一来源是 uv.lock，这里不写死：必须由构建方传入 --build-arg PLAYWRIGHT_VERSION。
# 用 docker/playwright/build.sh 构建，或让 CI 自动带上（见 .github/workflows/playwright.yml）。
# 直接 docker build 而不传这个 arg 会因为拉不到 playwright:v-noble 而失败。
#
# 必须与 uv.lock 里的 playwright 一致：nonebot-plugin-htmlrender 的 WS 版本闸门
# 要求 major 相同，minor 相差 >= 2 会直接拒绝连接。
ARG PLAYWRIGHT_VERSION

FROM mcr.microsoft.com/playwright:v${PLAYWRIGHT_VERSION}-noble

ARG PLAYWRIGHT_VERSION

ENV DEBIAN_FRONTEND=noninteractive TZ=Asia/Shanghai

# 远程模式下字体由浏览器端解析，所以 Sarasa Gothic 装在这里而不是 bot 镜像里。
# 基础镜像已经带了 curl 和 playwright install-deps 的字体集（含 CJK 兜底）。
RUN apt-get update \
  && apt-get install -y --no-install-recommends p7zip-full fontconfig fonts-noto-color-emoji \
  && curl -sSL https://github.com/be5invis/Sarasa-Gothic/releases/download/v1.0.32/Sarasa-TTC-1.0.32.7z -o /tmp/sarasa.7z \
  && 7z x /tmp/sarasa.7z -o/tmp/sarasa \
  && install -d /usr/share/fonts/sarasa-gothic \
  && install -m644 /tmp/sarasa/*.ttc /usr/share/fonts/sarasa-gothic \
  && fc-cache -fv \
  && apt-get purge -y --auto-remove p7zip-full \
  && rm -rf /tmp/sarasa /tmp/sarasa.7z /var/lib/apt/lists/*

# 三个浏览器已随基础镜像烘焙在 $PLAYWRIGHT_BROWSERS_PATH，这里只需要 CLI 本身
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

RUN npm install -g "playwright@${PLAYWRIGHT_VERSION}" && rm -rf /root/.npm

EXPOSE 3000

CMD ["playwright", "run-server", "--port", "3000", "--host", "0.0.0.0"]
