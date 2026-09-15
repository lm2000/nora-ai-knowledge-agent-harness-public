# Cloud foundation validation

[CLI guide](CLI.md) · [Qdrant guide](QDRANT.md)

The foundation has an offline test suite. It does not prove cloud permissions, networking, service readiness or successful recovery on a real target.

## Repeat the checks

From the repository root:

```bash
python3 -m unittest discover -s setup/google-cloud/tests -v
for script in setup/google-cloud/*.sh; do bash -n "$script" || exit; done
```

The historical suite contains 28 tests covering configuration/rendering and provisioning contracts. It uses temporary fixtures and mocked subprocess responses, without applying cloud changes. Shell checks parse commands without running them.

## Historical result

The September 5, 2026 validation recorded 28 passing tests, six preview invocations that never called a sentinel gcloud executable, and accepted local gcloud help syntax for 28 command variants. It also checked output preservation and invocation from a directory containing spaces.

These results support the prepared CLI. They do not validate a live project's billing, IAM effects, quota, resource JSON, Docker installation or Qdrant recovery. Saved operator configuration and prior plans remain in the private archive instead of public documentation.

## Runtime acceptance still needed

For a new target, confirm exact resource readback, authenticated Qdrant access and persistence of a synthetic record. Test restoration into a separate instance before relying on backups. A Nora answer and restored conversation require the separate application stack and its own tests.
