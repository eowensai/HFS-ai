#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
jar=tika-server-standard-3.3.2.jar
for suffix in '' .asc .sha512; do
  curl --fail --location --retry 3 "https://downloads.apache.org/tika/3.3.2/$jar$suffix" -o "$jar$suffix" ||
    curl --fail --location --retry 3 "https://archive.apache.org/dist/tika/3.3.2/$jar$suffix" -o "$jar$suffix"
done
curl --fail --location --retry 3 https://downloads.apache.org/tika/KEYS -o KEYS ||
  curl --fail --location --retry 3 https://archive.apache.org/dist/tika/KEYS -o KEYS
echo 'fb1f2fe57ac458b09d44d41d816f582e1d2fc93488acff6275caf414d8d5ef94e42166edc0b488dc2fb6ef3aa21fab62b107c43b9060385ff6d675e393c2c9e9  tika-server-standard-3.3.2.jar' | sha512sum -c -
mkdir -p .gnupg
chmod 700 .gnupg
gpg --homedir "$PWD/.gnupg" --batch --import KEYS
gpg --homedir "$PWD/.gnupg" --batch --status-fd 1 --verify "$jar.asc" "$jar" >signature-status.txt
grep -q '^\[GNUPG:\] VALIDSIG 184454FAD8697760F3E00D2E4A51A45B944FFD51 ' signature-status.txt
