# Tika 4 upgrade — September 11, 2026

> Subsequent application acceptance and current source/deployment status:
> [Python 3.14 / Streamlit 1.63 upgrade](APPLICATION_UPGRADE.md).

Status: local deployment implemented and automated validation complete; awaiting
user spot testing before publishing to `eowensai/HFS-ai`. This change starts from
`3c0c4ff` on `codex/tika-4-local-upgrade`; recent UI/reliability changes and existing
local source changes are preserved. No GitHub push or PR update has occurred yet.

## User benefit and limits

The model receives Markdown headings, lists and table structure, which better
preserves relationships such as spreadsheet system/owner rows. Tika 4 supplies
current parser dependencies and isolated workers. OCR/native tools remain, and
the app now recognizes the changed partial-result and error contract. The model
and its reasoning settings are unchanged. This is evidence of extraction and
integration compatibility, not a measured improvement in answer quality.

Tested Word/PDF/slide/spreadsheet/image content survives. Supported Office parsers
are used. Tika drops the observed Word comment author, so EphemerAI adds a labeled
attribution appendix from the standard top-level DOCX comment part in RAM. Its
XML input is capped at 1 MiB, declarations/entities are rejected, and read failures
mark the extraction partial. Duplicate comment text in the appendix is deliberate;
matching/replacing arbitrary body text could attribute another occurrence wrongly.
Comments in nested embedded Word files and every modern Office annotation variant
are not qualified by these tests. Cached spreadsheet values are used; no formula
recalculation or perfect layout/OCR accuracy is promised.

## Portable EphemerAI changes

- Pinned official Tika 4.0.0 full distribution, signed Ubuntu package updates and
  JSON configuration; distribution libraries/plugins retained. Removed obsolete
  XML, single-jar fetch script and non-SAX Office flags.
- `/tika/json/markdown`, `tk:content`, warning/exception/deadline/embedded-limit and
  partial-result handling; bounded JSON responses and preserved `ParsedText` API.
  Old header-based write limits and unused Python `tika` dependency removed.
- 50 MiB uploads, eight files/64 MiB per submission, 180-second client parsing,
  256 KiB text/file and 512 KiB/submission retained. Server has its own 262,144
  character limit; JSON wire allowance is separate from UTF-8 text capacity.
- Two 1536 MiB workers, 512 MiB parent, 150-second task/60-second progress limits,
  explicit temporary paths and IPC bounds, 6 GiB container/no swap. Existing
  logging, RAM storage and dump protections retained.
- Word comment attribution and escaped-whitespace empty-result fixes; focused
  regression tests. Test backend helper now supplies its synthetic tokenizer.
  Ruff uses explicit standard rules; existing semicolon violations in test tools
  were split so the required lint check passes. Browser upload assertions use
  accessible removal controls to tolerate abbreviated filename display.
- README, deployment guide, Tika build instructions, operations, privacy timeout,
  runtime lock and current-system/validation records updated. Rollback requires
  the previous **application and parser together**.

## Machine-specific deployment

Canonical Compose remains `/home/eko/ephemeral-llm/docker-compose.yml`. It pins the
Tika image digest and the app release tag (its exact digest is recorded) and builds the app from the preserved tested source
snapshot at `/home/eko/ephemeral-llm/releases/tika4-20260911`. It uses that snapshot's
static assets. The old source root remains intact; its stale application code is
not used for builds. The former `hfs-ai-live` app deployment is superseded by the
canonical `ephemeral-llm` project. Ollama was not recreated or reconfigured.

Exact image identities are in [runtime-lock.json](../deployment/runtime-lock.json).
Tika's JSON is embedded at `/etc/tika/tika-config.json`; the host recipe is at
`/home/eko/ephemeral-llm/deployment/tika`. Its old recipe/configuration is preserved
in adjacent `tika-before-4-20260911`. Tika has no published port; app uses Docker DNS
`http://tika-server:9998`. Observed IP `172.18.0.2` is not a permanent endpoint.

The existing Windows logon task starts WSL and refreshes forwarding; Docker
systemd startup and `unless-stopped` policies restore the containers. No host OS,
firewall or Windows startup-script change was necessary. HFS's systemd user unit
was stopped and disabled. Its dormant 8503 forward remains, with no HFS listener.
A full Windows/WSL reboot was not performed; service restart/startup controls and
Windows reachability were checked without interrupting the shared model.

For development checks only, an isolated Python venv and locally unpacked Ubuntu
browser libraries were used. They are outside the repository/runtime image and
are not production dependencies or persistent OS configuration changes.

## HFS Knowledge handoff

HFS is parked, with POC-B056 deferred in its own backlog. Its status, runbook,
execution-plan addendum and `docs/TIKA4_COMPATIBILITY_HOLD.md` record version,
image/config, endpoints, renamed content/embedded keys, request changes, partial
results, Office differences and endpoint rediscovery. `/rmeta` and per-request
configuration are disabled in the current server profile. **The EphemerAI 256 KiB
cap is unsuitable for unrestricted HFS ingestion.** HFS must choose appropriate
limits/profile and test its adapter before re-enabling intake.

HFS source documents, archived originals and product code were not touched.
Read-only before/after hashes matched for extraction runs, answers, evidence,
source memos, knowledge cards and database schema. No corpus regeneration,
database restore or model mutation was performed; existing research edits remain.

## Automated evidence

- `python -m pytest -q` and `pytest -q`: **365 passed** each.
- Python compilation, Ruff and dependency checks: passed; runtime Python Tika
  package removed. Source Markdown links and Compose configuration validated.
- All ten existing fictional fixtures: PDF, DOCX, PPTX, XLSX, PNG, JPEG and scanned
  PDF passed content checks; comparison found only formatting/thumbnail differences
  plus the corrected Word author loss. Spreadsheet relationships/cached formulas,
  Word notes/comments, added PowerPoint speaker notes and embedded ZIP text passed.
- Live ASCII server limit returned partial text and limit metadata. A 200,000-character
  Unicode input stayed below the server character cap but was capped at 262,143
  valid UTF-8 bytes by the app. Metadata/oversized-wire handling is covered by tests.
- Whitespace-only output, malformed PDF/ZIP, 11 MB spooling, HTTP 413 above 50 MiB
  and six concurrent requests passed. Disposable candidate with 250 ms task deadline
  returned HTTP 503 in 2.4 seconds, then served a healthy request; production uses
  150 seconds. No deliberate production OOM or 180-second wall-clock stall was run.
- Desktop/mobile browser smoke passed. Real upload-to-answer checks passed for
  text, >98 KB text with beginning/end markers and follow-up, image vision and
  scanned PDF OCR. Empty-file handling, copy/export, Thinking Mode reset and two
  independent sessions passed. A final deployed DOCX upload correctly answered
  with the recovered comment author and table values, followed by a successful
  follow-up and New Chat. Clipboard writes were intercepted in memory.
- Isolated browser failures covered parser timeout/failure, partial/mixed/same-name
  files, aggregate upload rejection, model busy/interrupted/timeout and context
  mismatch. These use synthetic services and do not interrupt Ollama.
- Runtime identity, CORS/XSRF, session cleanup setting, memory/no-swap/core/tmpfs
  checks passed, with zero container OOM kills. Scoped inspection confirmed the
  parent and both active worker JVMs mapped the no-dump library, had zero core
  limits, and workers used 1536 MiB heaps. HFS remained inactive/disabled.

Corrections found by validation: omit invalid empty request-log level; fit inline
bytes inside IPC payload; use `throwOnWriteLimit=true` to avoid the Tika 4.0.0
non-throwing handler's null-context exception; preserve comment attribution; treat
Markdown whitespace entities as empty. Actual limits/warnings were verified after
these corrections, rather than relying only on HTTP 200 or unit mocks.

## Paired rollback and publication

Retained on this host:

- App: `ephemerai:before-tika4-20260911@sha256:efb486b739c88686133f70009e63a47f1c14800c84c481e243890a7bb133e2b8`.
- Tika: `shared-tika:before-tika4-20260911@sha256:784a7f31e10139492bc22ccdbfbabc727a888ea3d851a1293723369333f8e09c` (3.3.2).

Use the paired [rollback override](../deployment/tika/rollback.compose.yml), with
both variables set to those digests, and recreate only the pair with
`--no-build --pull never --no-deps`. The override restores the old JVM heap profile while retaining container
temporary/memory/privacy settings. HFS
stays parked unless explicitly resumed. Baseline Compose/inspection records remain
local; image backups, runtime data, uploads, extracted content and secrets are
excluded from Git. Publication follows user feedback and affected revalidation.

The operator's spot test is one normal document question, a useful follow-up and
New Chat on the local UI. No file-format testing assignment remains for the user.
