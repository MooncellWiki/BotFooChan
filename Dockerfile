# syntax=docker/dockerfile:1

FROM python:3.12-bookworm AS requirements-stage

WORKDIR /tmp

RUN pip install -U pdm

ENV PDM_CHECK_UPDATE=false

COPY ./pyproject.toml ./pdm.lock /tmp/

RUN pdm install --check --prod --no-editable --with deploy

FROM python:3.12-bookworm AS metadata-stage

WORKDIR /tmp

RUN --mount=type=bind,source=./.git/,target=/tmp/.git/ \
  git describe --tags --exact-match > /tmp/VERSION 2>/dev/null \
  || git rev-parse --short HEAD > /tmp/VERSION \
  && echo "Building version: $(cat /tmp/VERSION)"

FROM python:3.12-slim-bookworm

WORKDIR /app

ENV TZ=Asia/Shanghai

ENV DEBIAN_FRONTEND=noninteractive

COPY --from=requirements-stage /tmp/.venv/ /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

COPY ./docker/start.sh /start.sh

RUN chmod +x /start.sh

COPY ./docker/gunicorn_conf.py /gunicorn_conf.py

ENV PYTHONPATH=/app

EXPOSE 8086

ENV APP_MODULE=bot:app

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl p7zip-full fontconfig fonts-noto-color-emoji \
  && curl -sSL https://github.com/be5invis/Sarasa-Gothic/releases/download/v1.0.30/Sarasa-TTC-1.0.30.7z -o /tmp/sarasa.7z \
  && 7z x /tmp/sarasa.7z -o/tmp/sarasa \
  && install -d /usr/share/fonts/sarasa-gothic \
  && install -m644 /tmp/sarasa/*.ttc /usr/share/fonts/sarasa-gothic \
  && fc-cache -fv \
  && apt-get purge -y --auto-remove curl p7zip-full \
  && rm -rf /tmp/sarasa /tmp/sarasa.7z /var/lib/apt/lists/*

RUN python -m playwright install --with-deps chromium \
  && rm -rf /var/lib/apt/lists/*

COPY --from=metadata-stage /tmp/VERSION /app/VERSION

COPY . /app/

CMD ["/start.sh"]
