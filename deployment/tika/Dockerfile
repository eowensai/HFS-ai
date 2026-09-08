# Official full image preserves OCR languages, fonts, GDAL and ImageMagick.
FROM apache/tika:3.3.1.0-full@sha256:d8e6ed96260ad89307a93195a1b856102987a818ac648502f8efbaf313d32470
USER 0
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -o APT::Get::Always-Include-Phased-Updates=true upgrade -y \
    && test "$(dpkg-query -W -f='${Version}' openjdk-21-jre-headless)" = "21.0.12+8-1~26.04" \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY tika-server-standard-3.3.2.jar /tika-server-standard-3.3.2.jar
RUN echo "fb1f2fe57ac458b09d44d41d816f582e1d2fc93488acff6275caf414d8d5ef94e42166edc0b488dc2fb6ef3aa21fab62b107c43b9060385ff6d675e393c2c9e9  /tika-server-standard-3.3.2.jar" | sha512sum -c - \
    && rm /tika-server-standard-3.3.1.jar
ENV TIKA_VERSION=3.3.2
COPY tika-config.xml /tika-config.xml
CMD ["-c", "/tika-config.xml"]
USER 35002:35002
LABEL org.opencontainers.image.title="Shared Tika 3.3.2 on updated Ubuntu 26.04 LTS" \
      org.opencontainers.image.version="3.3.2-20260907"
