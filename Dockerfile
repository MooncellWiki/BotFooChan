# syntax=docker/dockerfile:1

FROM python:3.14-bookworm AS requirements-stage

WORKDIR /tmp

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="${PATH}:/root/.local/bin"

COPY ./pyproject.toml ./uv.lock* /tmp/

RUN uv export --format requirements.txt -o requirements.txt --all-groups --no-editable --no-hashes --no-dev --no-emit-project

FROM python:3.14-bookworm AS build-stage

WORKDIR /wheel

COPY --from=requirements-stage /tmp/requirements.txt /wheel/requirements.txt

RUN pip wheel --wheel-dir=/wheel --no-cache-dir --no-deps --requirement /wheel/requirements.txt

FROM python:3.14-bookworm AS metadata-stage

WORKDIR /tmp

RUN --mount=type=bind,source=./.git/,target=/tmp/.git/ \
  git describe --tags --exact-match > /tmp/VERSION 2>/dev/null \
  || git rev-parse --short HEAD > /tmp/VERSION \
  && echo "Building version: $(cat /tmp/VERSION)"

# 管理后台的前端（web/），生成纯静态文件，最后拷进镜像由 bot 进程托管
FROM node:26-slim AS web-stage

WORKDIR /web

# Node 25 起不再自带 corepack，按 package.json 里的 packageManager 装 pnpm
COPY ./web/package.json /web/package.json

RUN npm install -g "$(node -p 'require("./package.json").packageManager')"

COPY ./web/ /web/

RUN --mount=type=cache,id=pnpm-store,target=/root/.local/share/pnpm/store \
  pnpm install --frozen-lockfile && pnpm generate

FROM python:3.14-slim-bookworm

WORKDIR /app

ENV TZ=Asia/Shanghai DEBIAN_FRONTEND=noninteractive PYTHONPATH=/app

COPY ./docker/start.sh /start.sh

RUN chmod +x /start.sh

COPY ./docker/gunicorn_conf.py /gunicorn_conf.py

EXPOSE 8086

ENV APP_MODULE=bot:app

# 浏览器与字体都不在这个镜像里：渲染走远程 Playwright Server（见 docker/playwright/）。
# 这里只保留 playwright 的 Python 客户端。
# 直接装 build-stage 打好的 wheel，不再读 requirements.txt：里面 git 来源的依赖
# 是 `name @ git+…` 的写法，pip 照着它装会去调 git，而 slim 镜像里没有 git
RUN --mount=type=bind,from=build-stage,source=/wheel,target=/wheel \
  pip install --no-cache-dir --no-index --no-deps /wheel/*.whl

COPY --from=metadata-stage /tmp/VERSION /app/VERSION

COPY . /app/

COPY --from=web-stage /web/.output/public /app/web/.output/public

CMD ["/start.sh"]
