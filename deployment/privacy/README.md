# EphemerAI conversation and container privacy controls

## Enforced application lifecycle

`session_lifecycle.py` uses Streamlit 1.56's documented
`st.cache_resource(scope="session", on_release=...)`. Each session owns its
mutable message list, upload buffers, and token cache. The release hook uses its
captured objects and a lock, never thread-local `st.session_state`. New Chat clears
only this resource and named conversation state, resets one-shot options, and
creates a fresh owner. Messages/token results arriving after release are dropped.
No global cache-clear operation is used. Tika no longer retains duplicate parsed
text or relies on lazy expiration. Shared metadata/client/asset caches remain.
Request/export/preview locals are scoped to `main()` rather than retained in the
script module. The application does not write chat, documents, or responses to disk.

## Actual disconnect timing and residual retention

A clean WebSocket closure triggers the session release hook when the server
processes the disconnect. Silent network loss normally takes up to approximately
60 seconds with `websocketPingInterval=30` (ping and timeout), plus scheduling.
`disconnectedSessionTTL=0` prevents reconnecting to the old conversation. The
underlying Streamlit session-storage TTL is lazy; it is NOT a scheduled eraser.
The resource hook releases app-owned payloads without waiting for that TTL or
another parse/user interaction.

In-flight requests can still hold local copies until cancellation/unwinding or a
network timeout. Tika's client timeout is 15 seconds; the model's timeout is 1800
seconds with zero SDK retries. These are network timeouts, not a hard wall-clock
limit on every active request. Framework upload/media/message queues, Python
allocator remnants, native parser buffers, and shared model CPU/GPU/KV buffers
have their own lifetimes. Disconnection does not promise zeroization or a fixed
absolute deadline for all such references. Shared inference is not unloaded on
New Chat, since HFS uses the same runner. Abrupt process failure may bypass hooks.

Browser memory/cache, OS clipboard, user-requested exports/downloads, Windows
paging, WSL/Windows crash reports, and storage remanence are outside the cleanup
guarantee. Private browsing is not forensic erasure. New controls do not erase
old swap, dumps, logs, or previously stored disk contents. HFS's own documents,
database, jobs, answers, and history intentionally remain persistent.

## Container controls and sizing

| Service | RAM and memory+swap | /tmp | /var/tmp |
|---|---:|---:|---:|
| EphemerAI | 2 GiB | 1 GiB | 256 MiB |
| Shared Tika | 6 GiB | 1 GiB | 256 MiB |
| Shared Ollama | 18 GiB | 1 GiB | 256 MiB |

The observed WSL allocation was 30.19 GiB. Before remediation, app peak cgroup
usage was about 211 MiB, Tika 671 MiB, and Ollama 24.68 GiB during loading. Ollama's
steady non-cache use was about 2.1 GiB, including roughly 1.6 GiB anonymous memory
and 408 MiB shared memory; its loading peak includes reclaimable model-file cache.
18 GiB leaves substantial working-memory headroom while allowing that file cache
to reclaim. Tika runs two JVMs, each with a 2 GiB heap ceiling, so 6 GiB covers both
heaps, native overhead, and bounded temporary files. Limits total 26 GiB, leaving
about 4.2 GiB for HFS and host services if all limits are approached. This is a
measured pilot baseline, not a capacity guarantee for arbitrary concurrent users,
maximum-size archives, or every model input. No host-exhaustion test is required.

Equal `mem_limit` and `memswap_limit` prohibit Linux swap. `memory.swap.max=0`
must be verified in each service's cgroup. tmpfs usage counts against that service's
RAM limit; `/dev/shm` retains Docker's bounded 64 MiB default. No extra GPU worker,
model retargeting, quantization change, or context reduction is involved.

`nodump.c` is a small local ELF constructor, loaded through `LD_PRELOAD` in all
three dynamic service executables and their inherited dynamic workers. It sets
`PR_SET_DUMPABLE=0` and core soft/hard limits to zero, failing startup if either
operation fails. This addresses WSL piped core handlers that ignore RLIMIT_CORE.
Java crash heap/core dumps are also disabled; JVM fatal-error reports go to tmpfs.
The policy does not constrain a privileged administrator, a process deliberately
re-enabling dumps, a future static executable ignoring LD_PRELOAD, or Windows
crash collection. Reverify it after service-image changes. No new Python/runtime
package is installed. Build using `sh deployment/privacy/build-nodump.sh` and keep
the generated library with the deployment (it is intentionally Git-ignored).

## Deployment and verification

1. Read current instructions and preserve any uncommitted changes. Save the current
   Compose/config/code and tag the current app image for rollback.
2. Discover all containers, HFS services, prototypes and their runtime roots. Inspect
   aggregate active jobs, backend connections, and runner slots. Old `running`
   database rows are not alone proof of a live request: verify process/socket/lock
   activity without editing those records.
3. After active requests finish, gracefully stop each HFS client service and stop
   EphemerAI. Do not delete data, clear logs, remove models, or run `compose down`.
4. Build the local library and the app image. Recreate shared services individually
   with `docker compose up -d --no-deps --force-recreate --pull never SERVICE`.
   Preserve endpoint discovery for clients; confirm addresses and profile.
5. Warm the existing pinned alias with bounded fictional inference, verify Tika
   parsing, then start the prior client services and EphemerAI. Compare aggregate
   HFS preservation counts and functional status before/after.

```bash
cd ~/ephemeral-llm
docker compose config -q
for service in ephemeral-app tika-server ollama; do
  docker exec "$service" sh -c 'cat /sys/fs/cgroup/memory.max /sys/fs/cgroup/memory.swap.max /sys/fs/cgroup/memory.swap.current; cat /proc/1/limits; mount | grep tmpfs'
done
docker exec ephemeral-app python -c 'import ctypes,resource; print(ctypes.CDLL(None).prctl(3,0,0,0,0),resource.getrlimit(resource.RLIMIT_CORE))'
```

Expected dumpability is `0`, core limits `(0, 0)`, swap maximum/current `0`, and
RAM maxima 2147483648 / 6442450944 / 19327352832 bytes. Check service/worker maps
for the policy library, core limits for every PID, `memory.events` for OOM kills,
and the unchanged runner arguments (66 GPU layers, 131072 context, Q8 KV,
Flash Attention, one slot, batch 128, embedded MTP). Exec probes inherit the same
policy, but inspect workers as well; a probe alone does not prove worker state.

## Rollback

Use a coordinated idle window again. Restore only this task's code/config hunks
from the saved baseline, preserving later/unrelated changes. The prior app image
can be selected with an image-only Compose override (`build` must not be invoked
for that rollback). Prefer retaining the no-swap/core/tmpfs controls when rolling
back application code. If a memory limit proves insufficient, measure the failing
service's peak and OOM counters, then propose a headroom adjustment that preserves
zero swap; do not automatically lift limits. Removing these controls restores the
previous privacy exposure and does not erase any data. No HFS database or model
volume rollback is part of this procedure.

## Sources

- [Streamlit session resources and release hook](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_resource)
- [Streamlit server configuration](https://docs.streamlit.io/develop/api-reference/configuration/config.toml)
- [Docker memory and swap constraints](https://docs.docker.com/engine/containers/resource_constraints/)
- [Docker tmpfs limits](https://docs.docker.com/engine/storage/tmpfs/)
- [Linux core dumps and piped-handler exceptions](https://man7.org/linux/man-pages/man5/core.5.html)

For complete fresh-host recovery and off-host archive handling, use the
[repository recovery guide](../../docs/RECOVERY.md). HFS code/data stay separate.
