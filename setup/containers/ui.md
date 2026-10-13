# Interaction

[Services](README.md) · [Setup](../README.md)

The browser lets a user ask a question, continue a topic or create a new conversation. For example, an Atlas conversation remains available after a page reload while a new topic gets a separate UUID.

One Next.js application uses CopilotKit and AG-UI through `/api/copilotkit`. Its server forwards authenticated requests to one Coordination backend. `/api/history/{thread_id}` reloads the current assistant history. There is no role picker, role-specific backend map or transfer route.

The `nis-assistant-thread` browser key stores the current UUID. Conversation content lives in PostgreSQL, not browser storage. Stored legacy role history remains outside this interface. Browser storage and origin checks do not provide tenant identities.

Server utilities read credentials at request time; production builds do not need credential files. Body limits and origin checks protect incoming requests, and unavailable services produce a useful error. The displayed prepared-document count comes from backend health.

[Validation](../../evaluation/VALIDATION.md) separates synthetic browser checks from real provider/corpus acceptance. [Deployment status](../private-deployment/STATUS.md) owns dated live results.
