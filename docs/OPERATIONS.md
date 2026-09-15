> September15 update: the selected departmental frontend/engine and current commands are in [CURRENT_DEPLOYMENT.md](CURRENT_DEPLOYMENT.md) and the [operator guide](../System%20Deployment%20Guide.md). Historical shared-stack commands below require the explicit `docker-compose.ollama-shared.yml`; bare Compose no longer selects Ollama. Earlier evidence retains its original cutoff.

> **Scope:** commands here operate the original shared Ollama stack. For the isolated FP4/DFlash profiles use [FP4 deployment](FP4_DEPLOYMENT.md). Do not start Ollama alongside FP4.

# Operations with shared services

EphemerAI owns its UI/session lifecycle. Ollama and Tika may serve other clients.
HFS Knowledge's data is intentionally persistent and is not cleared by EphemerAI.
The Docker project name, model volume and internal network are stable in Compose.

## Tika 4 compatibility hold

As of September 11, HFS Knowledge is stopped and its user service is disabled.
Leave it parked until its own backlog item POC-B056 restores compatibility and
sets suitable ingestion limits. The 256 KiB EphemerAI cap is unsuitable for
unrestricted HFS ingestion. Do not apply the normal restore-client step below
to HFS during this hold. See [the upgrade record](TIKA4_UPGRADE.md).

## App-only changes

Finish active EphemerAI requests, preserve source changes and a rollback image,
then rebuild/recreate only `ephemeral-app` with `--no-deps`. Do not stop/reconfigure
Ollama or Tika, recreate an alias, change GPU placement, run `compose down`, restart
Docker or shut down WSL merely to deploy an app/UI/documentation change. Publishing
this repository branch itself requires no live deployment.

## Shared backend or host maintenance

1. Discover all current clients through Docker, processes, user/system services,
   backend sockets and each application's aggregate job status. Read their current
   runbooks. GPU idleness alone does not prove there is no queued/active request.
2. Establish an idle window and prevent new admissions. Allow active uploads,
   extraction and generation to finish. Use HFS's aggregate `pilot-status`, not
   content-bearing database queries. Old running markers can be stale; corroborate
   with live process/socket/scan state and the supported drain. Do not rewrite them.
3. Gracefully stop or pause each affected client under its own supported procedure.
   HFS's recorded user unit uses SIGINT with a 1900-second stop allowance. V3's
   transient unit and runtime must be rediscovered; do not assume its old unit name,
   work envelope or process state still applies.
4. Recreate only the necessary shared service. Preserve model volumes, network
   exposure, accepted model identity, one-slot policy, privacy limits and HFS data.
5. Verify health, cgroup limits, core policy, tmpfs, pinned model identity and GPU
   profile. Use only bounded fictional functional checks, then restore clients.
6. HFS v2.2 caches discovered backend IPs and needs its supported restart when those
   addresses change. New clients should use validated discovery/Docker DNS rather
   than copying observed private IPs. Compare HFS preservation counts and health;
   do not regenerate its corpus as an unrelated maintenance step.

The repository's [dated inventory](CURRENT_SYSTEM.md) helps locate these services
but cannot authorize interruption of new work. The HFS source/runtime is external.

## Privacy operations

Use `scripts/verify_runtime.py` after creation/recreation. Check cgroup
`memory.swap.max=0` and `memory.swap.current=0`; equal Compose memory and
memory-plus-swap values are only the requested settings, not verification.
Keep `/tmp` and `/var/tmp` bounded and the no-dump library present. Recheck worker
library mappings/core limits after changing images. The helper compares Tika against the digest pinned for this installation in Compose
(including its `.env` setting). It verifies an app exec probe; detailed worker inspection may require a scoped elevated read.

The shared model keeps CPU/GPU/KV memory across requests; New Chat does not unload
it. Cleanup is application object release, not byte zeroization. Browser/Windows
storage and historical disk contents remain outside the stated guarantee.

## Windows access and startup

The current site accepts Windows UI traffic from any source reaching the approved
upstream network boundary. Startup refreshes only configured 8501/8503 forwards;
it never creates/widens firewall rules at login. The repo defaults to 8501 only;
include 8503 only when HFS is separately present. V3 8513 remains loopback-only.
Do not publish raw Ollama or Tika as a convenience fix for discovery problems.

The recorded task runs at Windows logon, not before a user logs in after reboot.
A headless boot/autologon/service redesign is a separate operational choice.
