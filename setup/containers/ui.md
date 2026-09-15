# Interaction

[Services](README.md) · [Setup](../README.md)

The UI lets a user ask a question, continue a conversation, or start a new one. It shows the prepared-document count returned by backend health rather than a hard-coded corpus size.

[One Next.js application](../../ui/app/page.tsx) uses CopilotKit and AG-UI. Its server proxies authenticated requests to Coordination, bounds incoming bodies, checks origins and translates unavailable services into a useful message. Credentials are read at request time by [server utilities](../../ui/lib/backend.ts); the production build needs no credential file.

The browser retains its thread ID locally. Coordination stores conversation content in PostgreSQL and returns history on reconnect. This is a personal-workspace interface; browser storage and an origin check do not establish user identities or tenant isolation.

The UI's tests, TypeScript check and production build pass. [Validation](../../evaluation/VALIDATION.md) separates synthetic browser checks from a complete live deployment.


The UI container routes each conversation to a role-specific Coordination/Deep Agent container (`role-knowledge`, `role-research`, `role-interview`). It stores the selected role and per-role thread IDs, proxies AG-UI and history calls by role, and supports explicit user-reviewed context transfer from one role to another. See [D167](../../Decisions.md#selected-target-separate-runtime-and-job-containers).
