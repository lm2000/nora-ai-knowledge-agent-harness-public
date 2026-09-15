# Install and operate a private instance

[Reference history](README.md) · [Shared installation](../README.md#run-the-application) · [Historical status](STATUS.md)

For a fresh host, follow the single shared setup procedure. For an existing host, preserve its working release and data first, then validate the new source on a separate target before changing the running installation.

```mermaid
flowchart LR
    source[Source snapshot] --> target[Fresh target]
    target --> data[Prepare and import]
    data --> check[Verify services]
    check --> trial[Conversation trial]
    trial --> restore[Restore trial]
```

## Acceptance

Use synthetic documents first. Verify authenticated MCP calls, a question and follow-up, a correction, a missing-evidence response, a reload and a backend restart. Inspect database and provider failures separately. Check the selected provider's actual usage rather than interpreting request counts as spending.

The source candidate has local framework and BGE/MCP checks plus an ARM Linux container trial with live Ollama answers and PostgreSQL restoration into a fresh volume. Tailscale client access, correction behavior and representative quality remain to test; [validation](../../evaluation/VALIDATION.md) owns those limits.

## Operate and recover

Keep prepared bundles, the pinned model receipt, provider configuration and application version with the installation record. The original documents remain external to the search index. A reproducible prepared bundle is useful for rebuilding Qdrant, but it is not a conversation backup.

Back up PostgreSQL through a consistent database backup, and verify restoration into a fresh database. Preserve Qdrant through a supported snapshot or rebuild it from the exact prepared bundle. Retain host credentials and the daily counter according to the installation's recovery needs; do not include them in a public source release.

On the source host, from the repository root, stop Coordination while recording a conversation backup:

```bash
umask 077
docker compose stop coordination
docker compose exec -T postgres pg_dump -U nora -d nora -Fc > nora-postgres.dump
```

On a separate target with its own project, empty PostgreSQL volume and initialized credentials, restore before starting Coordination:

```bash
docker compose up -d --wait postgres
docker compose exec -T postgres pg_restore --exit-on-error -U nora -d nora < nora-postgres.dump
```

Complete the shared setup's index import and application startup there. Compare a recorded conversation ID's exact history and ask a follow-up in that conversation. The local trial preserved four messages through restart and fresh-volume restoration, then appended the expected question and answer. Keep the original database until the restored instance passes its checks.

`docker compose down` stops the prepared stack without deleting named volumes. Keep an existing working release and backups until the replacement passes its checks. A process restart, persistence on the same volume and restoration into fresh storage are separate results.

No existing cloud host, provider configuration or database was changed by this source refactor.
