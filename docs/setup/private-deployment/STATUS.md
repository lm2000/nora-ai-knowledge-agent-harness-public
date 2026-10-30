# Private deployment status

## Configuration reference — 2026-10-21

This is a documentation reconciliation of the maintainer's saved operating
guide, not a new live-service check. It records the candidate's direct-NIS
compatibility path in Coordination and generation-pinned GCS release pointer.
The source package still includes the earlier LiteLLM gateway reference and
local-pin activation procedure. Their availability does not select a deployment.

Read back the effective services, overlays, release and collection before an
operator change. Earlier dated checks below retain their original configuration
and results; this documentation pass did not activate a release or change a service.


## Gateway web search, streaming and default acceptance — 2026-10-15

The candidate gateway now exposes saved `nis_web` / `web-search` at `/mcp/web`,
using the existing Ollama credential and returning bounded public titles, URLs
and excerpts. Saved Retrieval search/read remains unchanged. Fresh sessions with
the desktop app's bundled Codex client authenticated through the command-backed
bearer helper, with no injected gateway environment key or MCP transport/auth/
approval overrides. One search completed in 0.887 seconds; the combined
search/read/web answer appeared after 15.111 seconds. These are bounded timings,
not a benchmark.

Two LiteLLM 1.103.2 compatibility defects were reproduced and fixed. A mixed
reasoning/text chunk previously lost its text delta; chunks now separate before
Responses conversion. Ollama's nested function-call indexes were also discarded,
merging independent argument objects; provider indexes and IDs now survive.
Live checks verified 19 incremental answer deltas equal the final text, a
single-call round trip, and two independent calls followed by a correct joined
result. No final-buffer text replay is used. Five gateway tests pass against the
actual locked dependency, covering authenticated/bounded web behavior, sanitized
failures, mount ordering, mixed channels, arguments and stream interruption.
The project suite passes 284 tests and 11 subtests, with eight skips; two gateway
converter tests run separately inside the locked image.

Only the gateway was recreated. Its launcher and configuration disable schema
updates. A fresh readable PostgreSQL backup preceded rollout; all five NIS table
content hashes, database schema, other container IDs, and the 21,512-document /
143,123-point corpus remain unchanged. The older current-conversation recovery
gap below remains unresolved; this change did not restore or alter data.

An initial all-settings check exposed the independent-call defect; its temporary
default selection was rolled back. After the fix, an all-settings session passed
with direct tool mode, then the default was selected and a genuinely new session
passed with no provider, model, catalog, plugin or MCP overrides. It called saved
Retrieval and saved web search, returned the correct heading/document identity
and public URL, and completed its answer after 15.921 seconds. A fresh bundled
app server independently read `nis-litellm` / `nora-ollama` as the default. Existing
chats retain their selected model; no GUI restart or existing-chat migration is
claimed. Reasoning effort `high` keeps GLM's thinking separate from answer text.

Rollback retains the prior immutable gateway image, original Compose overlay
sequence and narrow Codex default-setting backup. Local source changes remain
uncommitted/unpublished; the website and all Founders detail are unchanged.
Private receipts, failed attempts and exact rollback instructions are retained in
`.private/litellm-routing-finish-20261015/` and canonical Operations Guidance.
The existing untracked `skills/` manifest mismatch still blocks whole-checkout
link/diagram checks; that tree was preserved. Remote-plugin refresh and unrelated
MCP-session cleanup warnings occurred after the successful default answer; they
did not prevent its required tool calls.

The allowlisted 179-file source export passes source/privacy validation, all 396
local links across 50 public documents, and structure checks for eight HTML/GIF
pairs. No source archive was published; diagram rendering was not rerun because
no diagram changed. These export checks do not hide the separate whole-checkout
manifest limitation above.

## Saved Retrieval MCP and routing-work checkpoint — 2026-10-15

The user-level Codex configuration now persists `nis_retrieval` with the
gateway `/mcp/retrieval` URL, the existing credential-header helper and explicit
approvals for `retrieval-search` and `retrieval-read`. TOML parsing and a fresh
Codex process accepted the saved configuration without endpoint, authentication
or approval overrides. The real search returned the expected Manual ingestion
source and the model answered with its exact heading and document identity.
Search took 0.759 seconds; the answer appeared after 12.24 seconds, including
one automatic retry following an upstream connection-close error. Gateway access
logs corroborate the model and MCP requests. Provider selection and a temporary
catalog were explicit subprocess settings; the default provider was not changed.

At the operator's consolidation checkpoint, the cloud implementation worker
was stopped before source edits, builds or deployments; no implementation
worker process remained. Web search has not been configured or verified, and
the streaming defect remains unresolved. Candidate gateway is still healthy on
`nora-gateway:route-20261015` with its existing four Compose overlays. Other
candidate services were not recreated. Preserve all existing worktree edits,
the untracked skills tree and prior rollback material for the new owner.

The private receipt `.private/litellm-routing-fix-20261015/retrieval-checkpoint.json`
contains the fresh session, timestamps, exact worktree/owner handoff, running
image/overlays, worker logs and remaining acceptance work. Earlier SSE evidence
is retained alongside it; no web-search or streaming completion is claimed.

## Opt-in Codex route verification and Python diagnosis — 2026-10-15

A fresh Codex subprocess using `nis-litellm` / `nora-ollama` executed
`retrieval-search` through the gateway's `/mcp/retrieval` endpoint and answered
the manual-ingestion question correctly: an operator starts the job; user
questions do not trigger ingestion. The answer included the exact supporting
heading and document identity. Matching gateway access logs show two successful
`/v1/responses` requests and the successful Retrieval MCP request.

The successful probe's search took 0.885 seconds, its answer appeared after
9.324 seconds, and the complete subprocess took 10.798 seconds. An initial
attempt was blocked by fresh-session tool approval; one corrective retry
approved the read-only search for that subprocess. The current saved Codex
configuration has no `nis_retrieval` entry, so the probe supplied it through
process-only overrides. The global configuration hash and default provider
were unchanged.

Web search through LiteLLM is not configured: the live gateway has no named
search tools or web-search MCP tool. A `/search` validation request returned
HTTP 500, requesting a search tool name or model; no web search executed.
Separate model-stream probes returned HTTP 200 in 1.558 and 1.611 seconds, but
text deltas were incomplete or absent. The second final text event carried the
correct answer after 1.567 seconds. Streaming behavior remains unresolved;
these isolated observations are not a reliability or latency benchmark.

The base Miniconda environment reports 11 dependency conflicts, mostly involving
older distributions. Active Hermes processes use their separate, dependency-clean
environment. The project's existing `nora-ai` environment also passes `pip check`;
`mise exec -- python -m pytest -q` passed 281 tests and 11 subtests, with six
skips. The earlier base-environment installation bypassed the documented project
environment; no packages were changed during this diagnosis.

Private evidence: `.private/litellm-route-20261015/receipt.json` and its adjacent
timestamped Codex events, model-stream observations and gateway access logs.
The custom-model warning remains unresolved; metadata registration is supported
through `model_catalog_json`, contrary to the earlier chat diagnosis. No default
switch, provider onboarding, database/schema change or deployment occurred.
Receipt parsing, credential-value scanning and `git diff --check` passed.
Both documentation checks remain blocked by the existing untracked `skills/`
Markdown files outside `public-docs.json`; that unrelated tree was preserved.

## LiteLLM inference and Retrieval routes — 2026-10-14

The candidate gateway was rebuilt as `nora-gateway:route-20261015` from the
gateway source and remained healthy after recreation. Its nonempty model list
contains `nora-ollama`, backed by the already configured Ollama Cloud
`glm-5.3-flash` route. Authenticated readback returned that model from
`/v1/models`; an authenticated `/v1/responses` request completed successfully.

The gateway also mounts the candidate Retrieval MCP as `/mcp/retrieval` using
the existing `mcp` secret. `tools/list` returned `retrieval-search` and
`retrieval-read`, and a real `retrieval-search` request returned the expected
Manual ingestion passages and embedded coverage. Coordination remains available
at `/mcp/nis` as `nis-ask_nis`.

The local user-level Codex configuration now contains an opt-in `nis-litellm`
provider and an opt-in `nis_retrieval` MCP server; the existing OpenAI default
was not changed. Codex-native web search, app connectors and the managed Codex
backend remain outside LiteLLM. Fireworks was not enabled because the candidate
has no nonempty `fireworks` secret; no fallback claim is made for it. Rollback
is to restore the prior gateway image and remove the opt-in provider/MCP entries.

[Setup](../README.md) · [Roadmap](../../Plan.md) · [Validation](../../evaluation/VALIDATION.md)

This is dated evidence, not a live monitor. Canonical maintainer Operations Guidance owns exact host configuration, active overlays and private receipts. Superseded diagnoses and trial sequences remain in Git history.

## LiteLLM Admin UI database repair — 2026-10-14

The candidate LiteLLM gateway now has a database-backed Admin UI. The gateway
constructs its PostgreSQL connection URL from the mounted `postgres` secret, and
the gateway image includes Prisma 0.15.0, the generated LiteLLM Prisma client and
the Debian `libatomic1` runtime library. The candidate gateway is healthy and the
private Admin UI returned HTTP 200; an authenticated browser check reached the
LiteLLM Dashboard as `admin`.

During the repair, an unrestricted Prisma schema sync against the shared NIS
database dropped five NIS checkpoint/ownership tables because LiteLLM's schema is
not the NIS schema. The gateway was stopped immediately. The five tables were
restored from the retained October 2 recovery backup (`nora-postgres.dump`);
that backup was created on October 2 and is older than the current candidate
state, so full current checkpoint recovery is not established. LiteLLM tables
remain present. Future initialization must use a current backup and a reviewed
additive migration or a separate LiteLLM database; do not use unrestricted
`prisma db push` against the shared NIS database.

## One-assistant rollout — 2026-10-02

The candidate runs one assistant with embedded FastMCP, a separate LiteLLM gateway and a browser UI without a role picker. Real direct/gateway questions and cross-path UUID continuation passed. Normal assistant/gateway restart preserved the conversation. Browser chat returned its marker, restored history after refresh and answered a contextual follow-up. The retained corpus, PostgreSQL state and separate baseline remained intact.

## Ordinary unrestricted OpenClaw acceptance — 2026-10-03

The selected bounded main-agent check passed with saved credentials, directory
Tool Search, the local Gateway and the full original tool policy. Ollama Cloud
`minimax-m2.7` discovered and invoked NIS. The initial call shortened the question,
dropping no-retrieval/reply-only instructions; its same-thread recall succeeded,
but that pair did not satisfy the full prompt contract. One exact-prompt corrective
pair returned `NIS_READY_FINAL_20261003` twice with UUID
`31d832a4-ed47-4b4f-9d5c-f1a66f7b82b9`. Persisted structured tool results confirm
both answers and UUID reuse; the corrected CLI turns report zero tool failures.
The test session has zero external delivery operations and the persistent config
SHA-256 remains unchanged. No temporary tool restriction or provider change was used.

Together with the prior fresh Codex check, this closes the bounded conversational
client-acceptance requirement. Initial prompt truncation remains a quality limitation;
this pass does not establish general reliability, a runtime no-retrieval trace, or
broad answer quality. Telegram stays deferred. No original-chat files or heartbeat
were changed. Private receipt: `.private/nis-openclaw-unrestricted-main-20261003.json`.


## Retained corpus and additive refresh — 2026-10-04

The original retained corpus contained 21,508 documents and 143,071 points. Additive assembly preserved it while adding three current-project sources; import verified 21,511 documents and 143,118 points before activation. A later recovery-source addition produced the current recorded 21,512 documents and 143,123 points.

The latest recorded prepared release is `full-20261004-recovery-r1`, with collection `nora_full_20261004_recovery_r1`. Retrieval uses an explicit data-directory pin. Activating a symlink alone cannot change this deployment; all current overlays must survive an explicit Retrieval activation. Only Retrieval changed during the additive activation; other service identities and inference routes were retained.

A saved-gateway ingestion question/follow-up passed after activation, covering the manual trigger, four stages, no question-triggered ingestion, no LLM source summaries and independent ingestion job state. This was one bounded pair, not representative quality acceptance. Corpus freshness is mixed: retained September 5 material plus selected October 4 source captures. GCS cutover remains pending.

## Bounded length repair deployed; focused recovery question passed — 2026-10-05

The graph recognizes explicit numeric word caps and can use one no-tool rewrite within the four-logical-model-call allowance. It never truncates or loops; exhausted allowance or a still-oversized/empty repair produces an error. Focused deterministic tests covered the fourth-call repair, failure paths, history cleanup and follow-up reset.

The original failed recovery question returned a nonempty, error-free 98/100-word answer naming the correct operating source/heading and preserving dated-evidence uncertainty. Its trace used Grounding, a short search, an offset-zero read, three model calls and two model-requested tool calls. The live reply was already compliant, so only deterministic tests exercised shortening. Capped streaming presentation remains unaccepted because streams can expose drafts.

## Preparation source attribution and coverage — 2026-10-06

The deployed source-attribution guidance keeps NIS/manual-ingestion terms in searches, reads missing requested titles at offset zero and explicitly addresses named triggers. Q1 passed at 100/100 words against the saved Manual ingestion source; its source-level automatic-activation description does not verify the current direct-pin deployment. Its same-UUID F1 passed in two sentences at 46/50 words, excluding question/folder-change triggers and Coordination ownership of ingestion job state.

Earlier Q2 trials omitted preservation fields or read the broader Architecture decisions source. The failed preparation-coverage overlay remains excluded. During the single-assistant cleanup, a 79-word answer read the correct Manual ingestion source but omitted source identity/metadata. Its bounded failed-turn trace contained 21 checkpoints; prior guidance was restored before the focused correction.

The corrected saved-gateway Q2 returned 81/100 whitespace-separated words, including attribution. It states deterministic preparation without source summaries or meaning rewrites, retaining originals, headings/substantive text, source metadata and stable text identities, chunk identities/hashes/offsets, and model configuration with vectors. It names **Manual ingestion / Processing contract** and **Selected target workflow**. The answer was checked against the saved source actually available to Retrieval. No successful-turn checkpoint trace was inspected. Private receipt: `.private/single-assistant-cleanup-20261006/q2-complete.json`.

## Single-assistant source cleanup and rollout — 2026-10-06

Removed multi-role configuration/routing, transfer operations, role-specific HTTP/UI routes, the unused historical corpus adapter and overlapping diagram pairs. Assistant HTTP/AG-UI and `ask_nis(question, optional thread_id)` remain. Stored historical role UUIDs are rejected without migrating or deleting conversations. The selector, three total retrieval calls, four logical model calls, graph completion and bounded length repair are retained.

Contributor validation passed: 166 Python tests and 11 subtests, six PostgreSQL-fixture skips, five UI tests, typecheck/build, lint/format, shell, links, eight diagram pairs and release manifests. Eight synthetic browser checks passed; changed diagram frames and HTML interactions were inspected.

Verified PostgreSQL/Qdrant backups, a complete prepared bundle copy and effective configuration preceded rollout. Only Coordination and UI changed. Other services, the retained 21,512-document / 143,123-point corpus, and existing assistant history remained unchanged. Backups are saved; restoration is unexercised. Exact images, effective overlays and private receipts are in canonical Operations Guidance and the private host runbook.

The fresh saved Codex gateway question and same-UUID follow-up passed across a normal Coordination restart. Existing assistant history remained byte-identical; corpus counts stayed unchanged. Ordinary OpenClaw main forwarded both exact prompts through its full saved tool policy using Ollama Cloud `minimax-m2.7`, without fallback, external delivery or persistent configuration changes. Its first visible reply added formatting around the correct marker; the follow-up displayed only the marker. This remains an instruction-following limitation rather than a failure of routing or continuity.

The changed live browser passed fresh chat, contextual follow-up, reload, separate-topic UUID, no browser errors and final visible/persisted-answer readback. The first harness assertion incorrectly assumed one assistant element per live tool turn; correcting the harness resolved it. A screenshot confirmed both persisted answers. Removed backend/UI role interfaces reject requests; an actual stored historical role owner receives 403.

Private receipts live under `.private/single-assistant-cleanup-20261006/`. Private main publication and clean primary synchronization were verified for implementation commit `f1cf8ec`. All 25 effective backend/health files and the UI build context match the checkout; a Coordination-only health mount replaces the older shared file. The final status-record commit, exact image/Git hashes and receipts are recorded in [the roadmap](../../Plan.md) and canonical Operations Guidance.

## Remaining acceptance limits

Representative answer quality, repeated reliability, real GCS refresh, incremental replacement/deletion and full clean-target restoration are not established by these checks. Ordinary ingestion is backup-first rather than a rollback procedure. Existing assistant conversations and corpus data remain in scope for continuity checks; legacy role chats are retained without migration or exposure. Telegram and the separate baseline remain outside the current cleanup.


## Focused quality correction rollout; acceptance failed — 2026-10-06

Coordination alone now runs `nora-candidate-backend:quality-correction-20261006` (`sha256:e747cd5fd1b3b7ce12ca8d989d004f23b47a0032f5da180ae0e04a15728f8957`). Only agent/assistant modules changed. A fresh readable PostgreSQL dump and reverified Qdrant/prepared/configuration backups preceded rollout. All prior overlays/health mount remain, with an image-only quality overlay last. Health, existing history, corpus counts and other services remained unchanged. Source changes remain uncommitted/unpublished; this image includes the local delta and does not match published main.

Four bounded saved-gateway turns returned Q2a 503, Q2b passing at 83/100 words, P4 passing at 99/120 words and a follow-up 503. Failed-turn traces alone (19/13 checkpoints) show empty repair generations at `done_reason=length`, 1,800 tokens; the new completion check rejected them. Diagnosis also found untitled owning-passage/title-recovery and model-configuration synonym gaps in the local implementation. The healthy candidate remains deployed but this quality correction is unaccepted. No additional trials, publication or primary synchronization occurred. Existing call/token/provider limits are unchanged. See [execution progress](../../Plan.md#execution-progress) and canonical Operations Guidance.


Quality refinement rollout (2026-10-06): Coordination image `quality-refinement-20261006` / `sha256:920485192ed9cd35fc49b745458793055203c1271b3f188d4a4315b58fb7b5a4` is healthy; existing history/corpus/other services and limits retained. Three preparation turns produced one pass (78/100 words) and two HTTP 503 failures. Failed-turn checks exposed substantive-content synonym rejection and a follow-up repair missing deterministic/no-rewrite and explicit source identity. Quality remains unaccepted; publication and primary synchronization remain pending. No extra trials; prior passing storage comparison retained. Canonical Operations Guidance contains the dated receipt/report reference.


Local preparation follow-up correction (2026-10-06): 67 focused tests and saved failed-draft replay pass. Supported substantive-content/boilerplate-aside wording is accepted; related restatement guidance retains all six facts. Genuine omissions remain rejected. This correction is undeployed and unpublished; running image 92048519 remains healthy but unaccepted. Real-model follow-up compliance and publication/primary synchronization remain pending. See canonical Operations Guidance for the dated result.


Preparation follow-up rollout (2026-10-06): Coordination image `preparation-followup-20261006` / `sha256:ffed46272d5e0798a6308410c8e7cc8f9dcdc29f7fb22346a8da146ecb02684f` is healthy; history/corpus/other services/settings retained. Both fresh Q2 calls failed with HTTP 503; follow-up returned all six facts/attribution at 87/100 words with an unsupported exhaustive opening. Initial first generation exhausted its token limit before repair. Second failure remains undiagnosed after a latest-turn diagnostic mistakenly read the successful follow-up; that boundary deviation is recorded in canonical Operations Guidance. Repeated preparation quality remains unaccepted; no publication or primary sync occurred.

## Request-only repair deployed and checked — 2026-10-13

Coordination now runs the verified request-only repair, six-field preservation guidance and Unicode source-heading comparison. Only agent, assistant and selector modules changed from the preceding image; their hashes match the published repair source. The image-only update preserved all previous Compose overlays, environment values, glm-5.3-flash model inventory and existing context/token/retrieval/model/repair limits. Other service identities were unchanged.

A fresh readable PostgreSQL dump and reverified retained Qdrant/prepared/configuration backups preceded deployment. Health is OK. The existing six-message assistant conversation is unchanged, and corpus counts remain 21,512 documents / 143,123 points. Two fresh saved-gateway questions and a follow-up passed at 71, 79 and 91 words with all six required facts and requested source headings. Saved new histories contain the exact answers and no internal repair instructions. No passing checkpoint traces were read. Rollback is prepared but was not exercised; full restoration and representative quality remain separate.

Coordination image: `nora-candidate-backend:answer-repair-20261013` / `sha256:9d8a3191ac37ad9bdfbe6e240d334c9be7ec6580e023bc7bfa74007df2fe50a7`. This scoped derivative patches three modules; it is not a fresh installation of the whole public package. The prior image is retained for image-only rollback. No ingestion, corpus activation, model-route or other-service change occurred.

## Candidate Retrieval moved to GCS — 2026-10-14

The verified live release `full-20261004-recovery-r1` was published to the
prepared GCS bucket and the generation-pinned `nora/releases/current.json`
pointer was advanced to that release. Candidate Retrieval was recreated with
the GCS pointer overlay; the other candidate services and Qdrant were not
recreated. Readback returned the same collection, 21,512 documents and 143,123
points. An authenticated MCP search returned the expected Manual ingestion
results with embedded coverage. The candidate stack remained healthy.

This completes the initial candidate GCS cutover. The legacy baseline stack is
separate and is not the selected candidate route. Future updates must publish
an entire verified release before advancing the pointer.
