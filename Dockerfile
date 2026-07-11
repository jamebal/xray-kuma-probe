FROM alpine:3.22 AS xray
ARG XRAY_VERSION=25.6.8
ARG TARGETARCH
RUN apk add --no-cache curl unzip \
    && case "$TARGETARCH" in amd64) arch=64;; arm64) arch=arm64-v8a;; *) exit 1;; esac \
    && curl -fsSL "https://github.com/XTLS/Xray-core/releases/download/v${XRAY_VERSION}/Xray-linux-${arch}.zip" -o /tmp/xray.zip \
    && unzip /tmp/xray.zip xray -d /out \
    && chmod 0755 /out/xray

FROM python:3.12-slim AS builder
WORKDIR /src
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update \
    && apt-get install --no-install-recommends --yes gosu \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system probe \
    && useradd --system --gid probe --home /app probe
COPY --from=xray /out/xray /usr/local/bin/xray
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
WORKDIR /app
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh \
    && mkdir -p /app/data /app/generated \
    && chown -R probe:probe /app
USER root
EXPOSE 8080
VOLUME ["/app/data", "/app/generated"]
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"]
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["xray-kuma-probe"]
