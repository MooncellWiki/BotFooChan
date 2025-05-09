# syntax=docker/dockerfile:1

FROM python:3.12-bookworm as requirements-stage

WORKDIR /tmp

RUN curl -sSL https://pdm-project.org/install-pdm.py | python -

ENV PATH="${PATH}:/root/.local/bin"

COPY ./pyproject.toml ./pdm.lock* /tmp/

RUN pdm export -o requirements.txt --output requirements.txt --without-hashes --with deploy

FROM python:3.12-bookworm as build-stage

WORKDIR /wheel

COPY --from=requirements-stage /tmp/requirements.txt /wheel/requirements.txt

RUN pip wheel --wheel-dir=/wheel --no-cache-dir --requirement /wheel/requirements.txt

FROM python:3.12-bookworm as metadata-stage

WORKDIR /tmp

RUN --mount=type=bind,source=./.git/,target=/tmp/.git/ \
  git describe --tags --exact-match > /tmp/VERSION 2>/dev/null \
  || git rev-parse --short HEAD > /tmp/VERSION \
  && echo "Building version: $(cat /tmp/VERSION)"

FROM python:3.12-slim-bookworm

WORKDIR /app

ENV TZ Asia/Shanghai
ENV DEBIAN_FRONTEND noninteractive

COPY ./docker/start.sh /start.sh
RUN chmod +x /start.sh

COPY ./docker/gunicorn_conf.py /gunicorn_conf.py

ENV PYTHONPATH=/app

EXPOSE 8086

ENV APP_MODULE bot:app

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl p7zip-full fontconfig fonts-noto-color-emoji \
  && curl -sSL https://github.com/be5invis/Sarasa-Gothic/releases/download/v1.0.30/Sarasa-TTC-1.0.30.7z -o /tmp/sarasa.7z \
  && 7z x /tmp/sarasa.7z -o/tmp/sarasa \
  && install -d /usr/share/fonts/sarasa-gothic \
  && install -m644 /tmp/sarasa/*.ttc /usr/share/fonts/sarasa-gothic \
  && fc-cache -fv \
  && apt-get purge -y --auto-remove curl p7zip-full \
  && rm -rf /tmp/sarasa /tmp/sarasa.7z /var/lib/apt/lists/*

COPY --from=build-stage /wheel /wheel

RUN pip install --no-cache-dir --no-index --find-links=/wheel -r /wheel/requirements.txt && rm -rf /wheel

RUN playwright install --with-deps chromium \
  && rm -rf /var/lib/apt/lists/*

COPY --from=metadata-stage /tmp/VERSION /app/VERSION

COPY . /app/

CMD ["/start.sh"]
