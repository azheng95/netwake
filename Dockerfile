FROM caddy:2.8-alpine AS caddy

FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    WEB_HTTP_PORT=26665 \
    WEB_HTTPS_PORT=26666 \
    APP_PORT=18080 \
    TLS_HOST=localhost \
    XDG_DATA_HOME=/tls \
    XDG_CONFIG_HOME=/config

RUN apt-get update \
    && apt-get install -y --no-install-recommends iputils-ping libcap2-bin \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY web/requirements.txt web/requirements.txt
COPY agent/requirements.txt agent/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY agent ./agent
COPY web/app ./web/app
COPY web/static ./web/static
COPY --from=caddy /usr/bin/caddy /usr/bin/caddy
RUN setcap -r /usr/bin/caddy
COPY proxy/Caddyfile /etc/netwake/Caddyfile
COPY runtime.py .

EXPOSE 26665 26666
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('APP_PORT', '18080') + '/healthz', timeout=2)"
CMD ["python", "runtime.py"]
