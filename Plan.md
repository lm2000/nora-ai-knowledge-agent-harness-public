# Roadmap

[Home](README.md) · [Deployment status](setup/private-deployment/STATUS.md) · [Evaluation](evaluation/README.md)

Nora is a private knowledge assistant with one runtime, shared retrieval services and a four-stage knowledge update workflow. Current work makes that system simpler, reproducible and measurable.

## Current architecture target

Use one NIS assistant with separate topic chats. The default access path is `client → LiteLLM MCP Gateway → NIS FastMCP server → NIS runtime`; the same FastMCP server can also accept direct client connections. NIS retains its selector, LangGraph execution and conversation ownership. See [the accepted target](Decisions.md#selected-target-one-assistant-with-a-gateway-backed-mcp-entrance).

Keep this private single-user integration simple; elaborate access-control and quota systems are outside the slice. Use one ask tool for new conversations, without old-chat migration. Embed FastMCP in the existing FastAPI process, calling shared NIS operations directly.

## Execution progress

### Source refinements awaiting deployment acceptance

- **Scoped preparation grounding:** targeted search and returned-ID read before generation for preservation questions.
- **Conservative text recognizers:** narrow English preparation contract matching for deterministic preparation, originals, headings, source identity, chunk metadata, and model configuration.
- **Unified completion and length repair:** reject empty length-stopped generations; share one tools-disabled repair within the four-logical-call allowance.
- **Shared retrieval accounting:** seed automatic Grounding operations into the per-turn retrieval counter; block parallel/sequential excess calls.
- **Assistant guidance:** prioritize the owning Manual ingestion guide over broader Architecture decisions; require explicit field coverage for preservation questions.

## Unresolved repair outcome

### Source release verification — 2026-10-13

The full source checks pass: 245 tests, six skips and 11 subtests. The extracted allowlisted public package passes 244 tests, six skips and 11 subtests; private `tests/test_server.py` is excluded by the manifest. Both source and package pass five UI tests, typecheck, production UI build, lint/format, shell syntax, local links, diagram structure and release scanning. Exact file inventory and all 176 source checksums match. These checks and the bounded acceptance support the source refresh; running services remain separate.

### Latest isolated acceptance — 2026-10-13

The current local request-only repair, six-field guidance and heading-whitespace correction passed two fresh preparation questions and one related follow-up in an isolated Ollama Cloud gpt-oss:20b process. Final answers were 67, 73 and 83 words; all three retained the six supported preservation fields and requested source headings after one no-tool repair. Each turn used two retrieval calls and two distinct model responses. All six responses were nonempty with normal stop. The second answer and follow-up used U+202F heading spaces, exercising the corrected comparison. No passing checkpoint diagnostics were read.

Production container/image/environment identities and installed source hashes matched before and after. Current local agent/assistant/selector hashes match the process inputs. Read-only retrieval and in-memory conversation/ownership stores isolated the run. Offline replay against the recorded retrieved evidence passes all three final answers. This establishes the selected bounded check, not general reliability or acceptance on the deployed glm-5.3-flash route. At acceptance time the source was uncommitted/unpublished; no deployment, corpus change or production conversation write occurred.

The initial cloud review misread explicit facts and added an unnecessary stage-number condition; its corrected answer-wording review confirms three passes. Both reports are retained, and evidence-based guard replay was checked separately. Private evidence: `.private/heading-whitespace-acceptance-20261013/`.

The request-only repair correction is implemented locally and passes 104 focused service, selector and assistant tests. The installed Ollama adapter serializes an actual repair request with a final user role while preserving the original system prompt and retrieved evidence. The internal instruction stays out of saved history/checkpoints and counts inside the existing context bound. Existing retrieval, model-call and single-repair checks pass.

A separate recorded single-turn check returned a nonempty repair but failed vector/configuration coverage. That record is retained alongside the three-turn result below.

**Isolated Ollama Cloud trial — 2026-10-12:** two fresh preparation questions passed at 76 and 80 words, both after one repair. The related follow-up returned an 85-word nonempty repair that omitted explicit deterministic preparation and was rejected. All three attempted repairs completed with normal stop and nonempty text; the earlier empty repair was not reproduced. Each turn used two retrieval calls and two distinct model responses. Only the failed follow-up's 13 checkpoints were inspected, within the 24 cap.

A later local edit now adds an explicit instruction to retain all supported requested preservation fields. The three-turn results above apply to the saved pilot source; that later edit was not exercised in this trial.

Preparation coverage remains unresolved. The next local check should validate the newly added preservation instruction against the captured follow-up fixture, including facts already present in the first draft. The initial model-configuration/vector matcher result also needs a narrow review against the actual list wording. Production container/image/environment identities and installed source hashes were unchanged. No service deployment, corpus update or source publication occurred.

### Local repair field-preservation guidance — 2026-10-12

The preparation-only repair request now rechecks all six supported requested preservation fields, rather than fixing only the named deficits. It explicitly includes model configuration retained with vectors. The captured vector-omitting repair remains rejected by the unchanged guard; a minimal wording correction passes the scripted check within 100 words. Generic length repairs keep their previous guidance. All 107 focused service, selector and assistant tests pass. Existing request-only message handling, context bounds, history isolation and call limits remain intact. This new guidance is local and has not been tested in another provider run; no new trial, deployment or publication was performed.


### Updated field-guidance isolated trial — 2026-10-12

The current local six-field repair instruction was exercised in a separate isolated Ollama Cloud gpt-oss:20b process. First fresh preparation question passed after repair at 63 words. Second fresh question returned a nonempty 79-word repair but the guard rejected its Selected target workflow attribution. Execution stopped at that failure; the related follow-up was not run. Both turns used two retrieval calls and two distinct normal-stop, nonempty responses. Only the failed second turn's 13 checkpoints were inspected.

The final rejected repair covers all six required preservation fields and names Selected Target Workflow with U+202F narrow no-break spaces. The literal heading check does not recognize those spaces. Offline replay of the exact saved repair reports only the heading deficit; normalizing whitespace on a diagnostic copy clears all deficits. The matcher and actual guard result remain unchanged. Follow-up acceptance remains untested for this source. Production container/image/environment identities and installed source hashes were unchanged; no deployment, publication, corpus update or production conversation write.

The smallest next local correction is Unicode whitespace normalization for source-heading attribution, with the captured failure and a missing-heading negative case as regression checks. No additional live trial was run. Private evidence: `.private/field-preservation-acceptance-20261012/`.

### Local source-heading whitespace correction — 2026-10-13

Source-heading attribution now collapses Unicode whitespace before comparing Manual ingestion, Processing contract and Selected target workflow. Returned answer text and preservation-fact checks are unchanged. The exact captured 79-word repair with U+202F narrow no-break spaces passes the actual guard locally; missing and misspelled workflow headings remain rejected. All 114 focused service, selector and assistant tests pass, with changed-file lint/format and a bounded Ollama Cloud review passing. This correction is uncommitted/unpublished and has not been exercised in another live acceptance trial. No deployment or corpus/conversation changes occurred.

## Later work

- Representative retrieval and answer-quality evaluation; bounded conversational checks do not establish general reliability.
- GCS prepared-document publication and pointer cutover, kept separate from ordinary local content updates.
- Incremental source replacement/deletion and concurrent-writer behavior; additions currently retain old source versions.
- Baseline retirement after its own backup and route review; outside this rollout.
- Capped streaming presentation: the JSON/MCP repair is bounded, but a stream may expose a draft before completion.
- Optional calendar/mail integration and additional deployment targets after a concrete need is established.
- Enterprise shared memory across harnesses, Kubernetes/SSO, commercial scale and measured customer AI latency are unimplemented/unverified.

Current decisions live in [Decisions](Decisions.md). Dated runtime and client evidence lives in [Deployment status](setup/private-deployment/STATUS.md). Superseded plans and detailed historical execution entries remain in Git history.