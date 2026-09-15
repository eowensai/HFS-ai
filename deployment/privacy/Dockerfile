FROM python:3.14.7-slim-trixie@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6 AS build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev && rm -rf /var/lib/apt/lists/*
COPY nodump.c /src/nodump.c
RUN cc -shared -fPIC -O2 -Wall -Wextra -Werror -o /libephemerai_nodump.so /src/nodump.c
FROM scratch
COPY --from=build /libephemerai_nodump.so /
