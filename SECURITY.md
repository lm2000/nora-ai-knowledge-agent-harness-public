# Security and data handling

[Home](README.md) · [Deployment reference](setup/private-deployment/README.md) · [Publication preparation](PUBLISHING.md)

Nora's current reference deployment serves one operator through private access. The repository does not establish a hardened public API or a multi-tenant authorization model.

## Trust boundaries

- The browser talks to Coordination through the application server.
- Coordination calls authenticated Retrieval MCP tools and the selected inference endpoint.
- Retrieval reads prepared documents and Qdrant; it does not execute instructions found in documents.
- Conversation checkpoints and prepared knowledge have separate storage and retention needs.
- Hosted inference sends selected question/history/context content to that provider. Self-hosted document storage alone does not imply that all processing stays on the host.

The shared Compose file mounts credentials per service and exposes only UI and Retrieval on loopback. This is a personal-workspace design; verify private access and egress on the actual target. Complete container startup and multi-user authorization are outside the current validation result.

## Operational checks

Use synthetic documents to test authenticated and unauthenticated requests, prompt-injection handling, missing evidence, request limits and recovery. Check every exposed route, including UI-to-agent and agent-to-retrieval paths. Apply dependency and image updates with relevant integration checks.

Protect original documents, prepared text, embeddings, conversation databases and backups according to their content. Query hashes are identifiers, not a substitute for a data-retention policy. Review trace content before enabling an external observability service.

## Report a vulnerability

Do not post credentials, private documents or working exploits against a live private installation in a public issue. Use a private security advisory if the repository offers one. Otherwise request a private reporting channel from the maintainer with a brief description that contains no sensitive payload.

Include affected versions, the trust boundary involved, impact, and a minimal synthetic reproduction when available. No response-time commitment or supported-version policy has been established yet.
