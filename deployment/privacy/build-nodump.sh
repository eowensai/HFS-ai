#!/bin/sh
set -eu
cd "$(dirname "$0")"
# Build beside the target and replace atomically: do not truncate a library that
# a running service may have mapped. Changed policies still require recreation.
tmp=$(mktemp .nodump.XXXXXX)
trap 'rm -f "$tmp"' EXIT HUP INT TERM
cc -shared -fPIC -O2 -Wall -Wextra -Werror -o "$tmp" nodump.c
chmod 755 "$tmp"
mv -f "$tmp" libephemerai_nodump.so
