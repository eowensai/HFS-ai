# Build Tika 4 for EphemerAI

The recipe starts from the official full distribution
`apache/tika:4.0.0-1-full@sha256:80072bb73dd320a9de9709beb0b16d14dd6d2680376f8d31e498f55b633ba593`.
It retains the launcher, `lib/`, plugins, fonts, OCR and native helpers. Signed
Ubuntu package updates are applied during the build; each build gets its own
validated digest. Do not substitute `latest` or download a lone runnable jar.

```bash
docker build -t ephemerai-tika:4.0.0-local deployment/tika
```

Follow the [installation guide](../../System%20Deployment%20Guide.md) to inspect and
pin the resulting digest as `TIKA_IMAGE` in the ignored `.env`. The validated build
uses Ubuntu 26.04.1, Java 25.0.4 and Tesseract 5.5.0. OCR languages are `eng`, `deu`,
`fra`, `ita`, `jpn`, `spa`, plus `osd`; ImageMagick and GDAL remain present. A future
OS-package refresh must be checked again; the fixed upstream digest alone does not
make changing Ubuntu repositories byte reproducible.

## HTTP and extraction contract

EphemerAI requests `PUT /tika/json/markdown` and reads `tk:content` from the JSON
object. The supported Office event/SAX parsers are used; removed non-SAX flags
must not be restored. A bounded, memory-only DOCX comment reader adds an explicit
author/text appendix because Tika 4.0.0 omits author attribution in the observed
fixture. Oversized or unreadable comment XML produces a partial-result warning.
The appendix shares the 256 KiB application extraction cap.

Configuration is embedded at `/etc/tika/tika-config.json` from the adjacent
[`tika-config.json`](tika-config.json). Only `/tika` and `/version` endpoint families
are enabled. Request logging is disabled by omitting `requestLogLevel`; setting
it to an empty string fails in 4.0.0. Filename and document metadata are not logged
or retained by the client. Per-request configuration and the `/pipes` API are disabled.
Former `writeLimit` request headers do not enforce limits in Tika 4.

| Control | Setting |
|---|---:|
| Entire Tika container / Linux swap | 6 GiB / zero |
| Parent JVM heap | 512 MiB maximum, 128 MiB initial |
| Forked parsing workers | 2, each 1536 MiB maximum heap, 128 MiB initial |
| Worker CPU hint | 2 active processors per JVM |
| Worker task / progress deadline | 150 / 60 seconds |
| Client parse deadline | 180 seconds |
| Wait for worker / worker startup | 5 / 60 seconds |
| Request size | 50 MiB |
| Server character limit | 262,144 SAX characters (markup overhead affects output length) |
| App extracted text limit | 262,144 UTF-8 bytes; separate from character count |
| App JSON response buffer | 1,638,400 bytes |
| Inline bytes / IPC payload | 10,000,000 / 16,777,216 bytes |
| `/tmp` / `/var/tmp` | 1 GiB / 256 MiB, RAM-backed |

`throwOnWriteLimit=true` is intentional: 4.0.0's non-throwing handler hit a null
parse-context exception at the limit. The throwing handler returns truncated JSON
content with a limit exception flag, which EphemerAI marks partial. Other warnings,
exceptions, embedded limits and partial-timeout results are also marked partial;
HTTP errors fail the attachment without retries. Empty Markdown whitespace entities
are treated as no readable text. UTF-8 truncation never creates broken characters.

Privacy controls remain in Compose: no published Tika port, Docker logging `none`,
zero container swap, no-dump preload for parent and child JVMs, disabled heap/core
dumps, and temporary/error-file paths in tmpfs. Do not point temporary paths at disk.

## Shared clients and rollback

The September 11 local upgrade deliberately parks HFS Knowledge. Its old adapter
and unrestricted-ingestion assumptions cannot use this setup safely. It must adopt
Tika 4 metadata, partial-result semantics, request configuration and endpoint
discovery, and choose its own extraction limits before intake resumes. Do not
re-enable it merely because `/version` responds. HFS data is preserved separately.

Retain both previous application and Tika images. Set `EPHEMERAL_ROLLBACK_IMAGE`
and `TIKA_ROLLBACK_IMAGE` to their validated local digest references, then use
[`rollback.compose.yml`](rollback.compose.yml) with the main Compose file and
`--no-build --pull never --no-deps` for only `ephemeral-app tika-server`. Roll back
both together, retaining memory/tmpfs/privacy controls. No model or HFS database
rollback is needed. The [change record](../../docs/TIKA4_UPGRADE.md) records local
arrangements and validation; normal app-only operations remain in
[shared operations](../../docs/OPERATIONS.md).

Official references: [Tika 4 release](https://tika.apache.org/4.0.0/index.html),
[server migration](https://tika.apache.org/docs/4.0.x/migration-to-4x/migrating-tika-server-4x.html),
[metadata migration](https://tika.apache.org/docs/4.0.x/migration-to-4x/metadata-changes-4x.html).
