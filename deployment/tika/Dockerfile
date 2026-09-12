# Full distribution includes Tika 4's launcher, lib/, OCR, fonts and native tools.
FROM apache/tika:4.0.0-1-full@sha256:80072bb73dd320a9de9709beb0b16d14dd6d2680376f8d31e498f55b633ba593
USER 0
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get -o APT::Get::Always-Include-Phased-Updates=true upgrade -y \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY tika-config.json /etc/tika/tika-config.json
WORKDIR /opt/tika-server
USER 35002:35002
ENTRYPOINT ["java", "-jar", "/opt/tika-server/tika-server-standard-4.0.0.jar"]
CMD ["-h", "0.0.0.0", "-c", "/etc/tika/tika-config.json"]
LABEL org.opencontainers.image.title="EphemerAI Tika 4.0.0 with bounded Markdown extraction" \
      org.opencontainers.image.version="4.0.0"
