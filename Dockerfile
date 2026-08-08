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
RUN --mount=type=bind,from=build-stage,source=/wheel,target=/wheel \
  pip install --no-cache-dir --no-index --no-deps --find-links=/wheel -r /wheel/requirements.txt

COPY --from=metadata-stage /tmp/VERSION /app/VERSION

COPY . /app/

CMD ["/start.sh"]
