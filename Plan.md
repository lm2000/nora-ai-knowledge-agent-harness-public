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

### Quality correction source validation — 2026-10-14

The named-guide selection and scoped follow-up/gap correction passed full source validation: 281 tests, six skips and 11 subtests. Its extracted public package passed 280 tests, six skips and 11 subtests; private test_server.py is outside the public manifest. Both passed five UI tests, typecheck, production build, lint/format, shell syntax, local links, diagram structure and the 176-file release scan. Exact extracted inventory and source checksums match. The source application modules match the earlier six-case isolated acceptance inputs.

The isolated cases were 92/120, 98/120, 70/80, 52/60, 29/30 and 15/20 words. The SLA case establishes an owning-guide read and a gap statement about inspected text; its 8,000-character prefix does not establish absence throughout the entire guide or corpus. Source publication does not deploy this quality correction. The prior request-only repair image remains the recorded running deployment; the named-guide/follow-up correction awaits its own rollout.

### Verified repair deployment — 2026-10-13

Coordination now runs the verified request-only repair, six-field preservation guidance and Unicode source-heading comparison. Only agent, assistant and selector modules changed from the preceding image; their hashes match the published repair source. The image-only update preserved all previous Compose overlays, environment values, glm-5.3-flash model inventory and existing context/token/retrieval/model/repair limits. Other service identities were unchanged.

A fresh readable PostgreSQL dump and reverified retained Qdrant/prepared/configuration backups preceded deployment. Health is OK. The existing six-message assistant conversation is unchanged, and corpus counts remain 21,512 documents / 143,123 points. Two fresh saved-gateway questions and a follow-up passed at 71, 79 and 91 words with all six required facts and requested source headings. Saved new histories contain the exact answers and no internal repair instructions. No passing checkpoint traces were read. Rollback is prepared but was not exercised; full restoration and representative quality remain separate.

### Production-model isolated compatibility — 2026-10-13

Published repair source was checked in a separate in-memory process using the unchanged deployed Ollama Cloud glm-5.3-flash model spec. Two fresh preparation questions and one related follow-up passed at 67, 74 and 82 words. First turn used one repair; the second and follow-up passed directly. Each used two retrieval calls. Four distinct provider responses were nonempty and normal-stop. Saved-source replay confirms all six fields and requested headings. No passing checkpoint diagnostics were read.

The bounded cloud semantic review passed with a wording limitation: the follow-up's “nothing else is documented” phrase is too absolute because the source also lists full prepared documents and a manifest as artifacts. Required-field acceptance does not establish completeness of all additional artifacts or general reliability. Production container/image/environment and installed-source hashes were unchanged. Application source hashes match published source. No deployment, publication, corpus update or production conversation write occurred. Private evidence: `.private/glm-repair-acceptance-20261013/`.

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

Source-heading attribution now collapses Unicode whitespace before comparing Manual ingestion, Processing contract and Selected target workflow. Returned answer text and preservation-fact checks are unchanged. The exact captured 79-word repair with U+202F narrow no-break spaces passes the actual guard locally; missing and misspelled workflow headings remain rejected. All 114 focused service, selector and assistant tests pass, with changed-file lint/format and a bounded Ollama Cloud review passing. At that local check, the correction was uncommitted/unpublished and had not yet been exercised in another live acceptance trial. No deployment or corpus/conversation changes occurred.

### Varied gateway quality sample — 2026-10-13

Exactly six cases completed within their word caps: preservation/artifacts106/120, related artifact follow-up115/120, missing SLA/retention evidence80/80, same-chat topic change57/60, short operational answer26/30, and short follow-up14/20. Four cases passed the selected checks. Two need attention: the artifact follow-up retains an unsupported exhaustive opening, and the missing-evidence answer names a broader ingestion section rather than establishing the requested owning-guide reference and widens its gap claim to current deployment knowledge. No numeric SLA/retention values were invented.

Production container/image/environment identities were unchanged. No application, prompt, model, deployment or publication change occurred; no extra question or passing checkpoint trace. Three new test conversations were saved. Cases used the already-public ingestion guide; assessment used predefined criteria and visible-answer observations, not an independent full semantic judge or actual retrieved-passage inspection. The saved guide may be older, so this does not establish complete corpus gaps or general reliability. Results were saved in the private quality-sample receipt before proposing any correction.

### Local quality correction proposal — 2026-10-13

A draft proposal addresses unsupported exhaustive artifact follow-up wording and explicit Manual ingestion guide selection for gap questions. The proposed lookup reuses the targeted query/returned-ID/offset-zero read within the existing budget, independently of the six-field preparation check. An offline check confirms the exact SLA question has preparation_scope false; its actual live retrieval trace was not inspected. Proposed examples keep additional artifacts and missing-information statements tied to the passages inspected.

This is a proposal only: no application edit, live question, deployment, model or corpus change. Public code/guide and generic observations were used for cloud drafting; no private excerpt or raw live transcript was exported. Local implementation estimate:20–35minutes; a later six-case check is a separate10–20minute scope. The proposal and receipt are saved in the private quality-correction deliverable.

### Local quality correction implemented — 2026-10-13

The source now targets current questions explicitly naming the Manual ingestion guide with the existing targeted query and returned-ID/offset-zero read. The selection scope stays separate from preparation_check: a named-guide SLA question reads the candidate when available without requiring the six preservation fields. Generic questions and later unrelated topics retain their ordinary search. Candidate/title checks and shared three-retrieval/four-logical-model/one-repair/history/context limits remain unchanged.

Assistant guidance now includes requested artifacts supported by retrieved passages without unsupported exhaustive claims, and confines missing-information wording to the passages inspected. All 150 focused service, selector and assistant tests pass, including actual graph read/budget/reset, broader/missing candidates, current-topic scoping, exact short-answer follow-up and saved-history checks. Lint/format and bounded cloud code review pass. The reviewer incorrectly described the unchanged candidate selector as a title-substring match; it uses exact normalized title matching. No new gateway question, deployment, publication or model/corpus change. At implementation-check time this correction was uncommitted/unpublished; scripted replies do not establish real-model compliance.

### Updated-source isolated six-case check — 2026-10-13

The local quality correction passed all six selected cases on unchanged production glm-5.3-flash configuration in a process-only source overlay with in-memory conversations/ownership. Results: artifacts 92/120 words, artifact follow-up 98/120, named-guide SLA gap 70/80, same-chat topic change 52/60, short operational answer 29/30 and short follow-up 15/20. Each used one distinct nonempty normal-stop model response and no repair. The first five used two retrieval calls; the final unscoped follow-up used one.

The artifact follow-up retains the preservation fields and documents/manifest without the earlier nothing-else claim. The SLA case reads a returned owning-guide ID at offset zero and confines its final gap statement to retrieved text. Its read was the first 8,000 characters with a next offset, so absence across the entire guide/corpus remains unestablished. Actual read metadata establishes the owning guide for this sample; no passing or failed checkpoint traces were read. No additional semantic-review export was performed.

Production container/image/environment identities and installed source hashes were unchanged. Current local module hashes match the tested inputs. No production conversation write, source publication, corpus update, model change or deployment occurred. At this isolated check the correction was uncommitted/unpublished; this is one bounded sample, not general reliability evidence. Private receipt and exact answers are retained in the quality-correction acceptance deliverable.

## Later work

- Representative retrieval and answer-quality evaluation; bounded conversational checks do not establish general reliability.
- GCS prepared-document publication and pointer cutover, kept separate from ordinary local content updates.
- Incremental source replacement/deletion and concurrent-writer behavior; additions currently retain old source versions.
- Baseline retirement after its own backup and route review; outside this rollout.
- Capped streaming presentation: the JSON/MCP repair is bounded, but a stream may expose a draft before completion.
- Optional calendar/mail integration and additional deployment targets after a concrete need is established.
- Enterprise shared memory across harnesses, Kubernetes/SSO, commercial scale and measured customer AI latency are unimplemented/unverified.

Current decisions live in [Decisions](Decisions.md). Dated runtime and client evidence lives in [Deployment status](setup/private-deployment/STATUS.md). Superseded plans and detailed historical execution entries remain in Git history.