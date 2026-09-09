# Build the maintained shared Tika service

Build Tika during installation; no saved container archive is required. The recipe
starts from the pinned official full image
`apache/tika:3.3.1.0-full@sha256:d8e6ed96260ad89307a93195a1b856102987a818ac648502f8efbaf313d32470`.
It preserves OCR, fonts and native helpers on Ubuntu 26.04 LTS, updates signed OS
packages, requires released OpenJDK 21.0.12, and installs signed Apache Tika 3.3.2.

## Build and pin

From the repository root, with curl, GnuPG and coreutils installed:

```bash
bash deployment/tika/fetch-artifact.sh
docker build -t shared-tika:3.3.2-local deployment/tika
```

The fetch script verifies the jar's fixed SHA-512 and Apache signer fingerprint;
the Dockerfile checks the checksum again. Downloads are ignored by Git. It checks
the current Apache download server and archive server, so an older maintained
release can still be fetched after moving out of the current download directory.

Inspect OS, Java and OCR availability using the commands in the
[installation guide](../../System%20Deployment%20Guide.md). Record the validated
local image as `TIKA_IMAGE=shared-tika:3.3.2-local@sha256:...` in the installation's
ignored `.env`. The guide supplies the exact command to generate that value.

This preserves digest pinning while allowing a fresh build to have its own digest.
The fallback in Compose retains the current host's September 7 image identity;
new installations do not need that old image. Never replace a digest with `latest`
or use an old unsupported base as a convenience workaround.

Ubuntu repositories advance. If the explicit Java version assertion fails, inspect
the newly available signed package/security release before updating that assertion.
A maintained newer Java release needs validation; removing the assertion or assuming
that every package in an LTS image is vulnerability-free is not an acceptance check.

## Compatibility and privacy

`tika-config.xml` keeps `useSAXDocxExtractor=false` and
`useSAXPptxExtractor=false`. The September 7 comparison found that Tika 3.3.2's new
SAX defaults changed comment attribution, note placement and ordering. These
supported flags preserved all 20 client text comparisons across ten fictional
fixtures. Spreadsheet formulas use cached values rather than recalculation.

OCR data remains available for `eng`, `deu`, `fra`, `ita`, `jpn`, `spa`, plus `osd`.
ImageMagick, GDAL, fonts and native helpers remain supplied by the full image.
Availability is not a guarantee of linguistic accuracy or support for every layout.

Tika has no published host port and Docker logging is disabled. The service uses
bounded `/tmp` and `/var/tmp` tmpfs, zero Linux container swap, the no-dump preload
policy, and JVM heap/core-dump disabling. Fatal JVM reports go to tmpfs. Do not
introduce document logging or persistent document-temporary paths. App timeout
remains 15 seconds; do not remove it to hide a parser regression.

## Updates on an existing shared host

Follow [shared operations](../../docs/OPERATIONS.md): finish extraction work,
coordinate dependent clients, rebuild/validate a candidate, record its new digest,
and recreate only Tika in the maintenance window. HFS v2.2 caches private backend
addresses and needs its supported graceful restart if an address changes. The
September 7 V3 assessment found no direct Tika client, but rediscover current
clients instead of assuming that remains true. Preserve all HFS data.

The recorded `rollback.compose.yml` is an emergency override for the previous
unsupported image. It is historical incident information, not a fresh-install
requirement. Prefer the last validated maintained image for rollback and retain
the current memory/core/tmpfs/network settings.

Official references: [Apache downloads](https://tika.apache.org/download),
[Apache security](https://tika.apache.org/security.html),
[Ubuntu security notices](https://ubuntu.com/security/notices).
