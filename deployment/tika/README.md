# Shared Tika 3.3.2 maintenance and recovery

The accepted image is
`shared-tika:3.3.2-20260907@sha256:784a7f31e10139492bc22ccdbfbabc727a888ea3d851a1293723369333f8e09c`.
It is locally built and **not published to Docker Hub**. Compose deliberately
refuses a pull. The exact image is included in the separate recovery assets made
by `scripts/recovery.py capture`; see [recovery](../../docs/RECOVERY.md).

## Exact recovery

Load the verified recovery assets through the fresh-host restore procedure. This
restores the accepted image without needing a package repository or jar download.
It does not restore HFS documents/databases. Check `docker image inspect
shared-tika:3.3.2-20260907 --format '{{.Id}}'` against the ID above before startup.
A GitHub source ZIP by itself does not include this multi-layer image archive.

## Rebuilding a candidate

The source recipe starts from the pinned official full image
`apache/tika:3.3.1.0-full@sha256:d8e6ed96260ad89307a93195a1b856102987a818ac648502f8efbaf313d32470`.
That supplies Ubuntu 26.04 LTS, native parser tools, fonts and OCR models. The
recipe upgrades signed Ubuntu packages, asserts OpenJDK 21.0.12, and installs the
signed Apache Tika 3.3.2 jar. The download script pins the jar's SHA-512 and the
Apache signer fingerprint. The Dockerfile rechecks the jar independently.

```bash
bash deployment/tika/fetch-artifact.sh
docker build -t shared-tika:3.3.2-candidate deployment/tika
```

Requires curl, GnuPG and coreutils on the build host. Build only as a candidate:
APT repositories advance, and the exact Java assertion intentionally fails after
version drift. Review the newer signed package/security release before updating
the assertion. Do not remove the check merely to make a build pass. A rebuilt
image has a new identity; validate, record the new digest and update Compose and
`deployment/runtime-lock.json` together in a coordinated change. Never retag it
as the exact saved image without validation.

## Compatibility and privacy

`tika-config.xml` explicitly keeps `useSAXDocxExtractor=false` and
`useSAXPptxExtractor=false`, preserving accepted comment attribution, note placement,
slide/table order and extraction interpretation while using the newer parser.
Spreadsheet formulas use cached values rather than recalculation. The full image
keeps OCR models for eng, deu, fra, ita, jpn, spa and osd; availability is not a
linguistic-accuracy guarantee. Native helpers, ImageMagick, GDAL and fonts remain.

The server is internal-only. `/tmp` and `/var/tmp` are bounded tmpfs, the cgroup
forbids swap, and the inherited no-dump policy covers the JVM and dynamic workers.
JVM heap/core dumps are disabled and fatal-error reports go to tmpfs. Docker logs
are disabled. Do not add document logging, persistent temporary storage or published
ports. App timeout is 15 seconds; do not retry without it to hide parser problems.

## Validation and maintenance

Use freshly generated fictional files for TXT, PDF, DOCX and image OCR; the latest
privacy validation passed both actual HFS and EphemerAI adapters for fresh PNG/PDF
buffers. Historical maintenance also checked OOXML comments/notes/order and cached
spreadsheet formula behavior. These are bounded functional checks, not certification
for every archive, document layout or language.

Read [shared operations](../../docs/OPERATIONS.md) before replacing Tika. HFS v2.2
may cache its IP at launch; finish active extraction, use its supported graceful
drain, replace only the intended container, verify both clients, then restore them.
Do not change HFS data or alter shared Ollama merely to validate the parser.

`rollback.compose.yml` records an old emergency image override from the earlier
maintenance. It reintroduces the older parser/OS exposure and is not a normal
recovery target. Prefer the current verified recovery archive; any downgrade needs
an explicit coordinated incident decision.

Official references: [Apache releases](https://tika.apache.org/download),
[Apache security](https://tika.apache.org/security.html),
[Ubuntu security notices](https://ubuntu.com/security/notices).
