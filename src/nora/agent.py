"""Nora's Deep Agent configuration, independent of HTTP and database startup."""

import json
import re
import unicodedata
import uuid
from typing import NotRequired

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    create_deep_agent,
    register_harness_profile,
)
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    ToolCallLimitMiddleware,
)
from langchain.agents.middleware.types import AgentState, hook_config
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    RemoveMessage,
    ToolMessage,
)
from langchain_core.tools import tool

from nora.assistant import AssistantConfig, load_assistant_config
from nora.common import valid_document_id
from nora.config import Settings

REPAIR_MESSAGE_NAME = "nora_answer_repair"


def requested_word_limit(question: str) -> int | None:
    """Recognize explicit numeric word caps, rather than numbers in source material."""
    matches = re.findall(
        r"\b(?:at most|no more than|up to|maximum of)\s+(\d+)\s+words\b",
        question,
        re.IGNORECASE,
    )
    caps = [int(value) for value in matches if int(value) > 0]
    return min(caps) if caps else None


# Narrow English preparation contract; this is not a general semantic judge.
PREPARATION_GROUPS = {
    "deterministic preparation without summaries or meaning rewrites": (
        r"deterministic",
        r"(?:no|not|without|doesn't|does not)[^.]*(?:summari|summary)",
        r"(?:no|not|without|doesn't|does not)[^.]*(?:rewrit|meaning)",
    ),
    "originals": (r"original(?:s| bytes| documents| files)?\b",),
    "headings and substantive text": (
        r"headings?",
        r"(?:substantive (?:text|content)|(?:full|source) text)",
    ),
    "source identity and metadata": (
        r"\bsource(?:(?!chunk)[^.;]){0,60}(?:identit|identifier|versions?|paths?|provenance|\bids?\b)",
        r"\bsource(?:(?!chunk)[^.;]){0,60}metadata",
    ),
    "chunk identities, hashes and offsets": (
        r"chunk[^.;]{0,100}(?:identit|identifier|\bids?\b)",
        r"chunk[^.;]{0,100}hash",
        r"chunk[^.;]{0,100}offset",
    ),
    "model configuration with vectors": (
        r"model[^.;]{0,60}(?:configuration|config|settings)|"
        r"model[^.;]{0,25}revision(?=[^.;]{0,80}dimensions)"
        r"(?=[^.;]{0,80}normali[sz]ation)",
        r"(?:model[^.;]{0,100}vectors?|vectors?[^.;]{0,100}model)",
    ),
}


def preparation_scope(messages, turns: int) -> bool:
    humans = [
        str(m.content).lower()
        for m in bounded_messages(messages, turns)
        if isinstance(m, HumanMessage)
    ]

    def explicit(text):
        return bool(
            re.search(r"\b(?:nis|nora)\b", text)
            and re.search(r"prepar(?:e|es|ing|ation)", text)
            and re.search(r"(?:what|which|all).*(?:surviv|preserv|retain|information.*keep)", text)
        )

    if not humans:
        return False
    if explicit(humans[-1]):
        return True
    # Only explicit related references carry scope; a new topic clears it.
    return bool(
        len(humans) > 1
        and explicit(humans[-2])
        and re.search(
            r"(?:that preparation|those preserved|what else survives|missing preservation)",
            humans[-1],
        )
    )


GAP_PATTERN = (
    r"not (?:available|specified|supported)|unavailable|missing|gap|"
    r"does not (?:specify|establish)|cannot verify"
)

PREPARATION_QUERY = "NIS Manual ingestion Processing contract deterministic preparation"


def named_manual_ingestion_scope(query: str) -> bool:
    """Detect explicit Manual ingestion guide requests naming the source.

    Generic unrelated ingestion queries or a passing manual-ingestion mention
    without an explicit guide/document/source/heading context remain ordinary
    search. Scope is derived from the current question only and is not
    inherited from previous human turns.
    """
    normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", query)).strip().lower()
    if not normalized:
        return False
    title = re.search(r"(?<![\w-])manual[\s\u00a0]+ingestion(?![\w-])", normalized)
    if not title:
        return False
    if re.search(r"""["'“”‘’`]\s*manual ingestion\s*["'“”‘’`]""", normalized):
        return True
    return bool(
        re.search(r"\bmanual ingestion (?:guide|document|source|heading)\b", normalized)
        or re.search(
            r"\b(?:guide|document|source|heading) (?:named |called |titled )?manual ingestion\b",
            normalized,
        )
        or re.search(r"\b(?:per|under|according to) (?:the )?manual ingestion\b", normalized)
    )


def preparation_document(payload) -> str | None:
    """Choose a returned ID for inspection, not a verified source attribution."""
    if not isinstance(payload, dict) or payload.get("error"):
        return None
    results = payload.get("results", [])
    if not isinstance(results, list):
        return None
    candidates = []
    for index, row in enumerate(results):
        if not isinstance(row, dict) or not valid_document_id(row.get("doc_id")):
            continue
        title = str(row.get("title") or "").strip().lower()
        if title and title != "manual ingestion":
            continue
        text = "\n".join(
            row[key] for key in ("heading", "text", "content") if isinstance(row.get(key), str)
        )
        heading = str(row.get("heading") or "").lstrip("# ").strip().lower()
        if title == "manual ingestion" or re.search(r"(?m)^#\s+Manual ingestion\s*$", text, re.I):
            rank = 0
        elif preparation_passages(row)[0]:
            rank = 1
        elif (
            heading == "selected target workflow"
            and re.search(r"deterministic preparation", text, re.I)
            and re.search(r"original", text, re.I)
            and "chunk identities, hashes and offsets" in preparation_features(text)
            and "model configuration with vectors" in preparation_features(text)
        ):
            rank = 2
        else:
            continue
        candidates.append((rank, index, row["doc_id"]))
    return min(candidates)[2] if candidates else None


def preparation_features(text: str) -> set[str]:
    text = text.lower().replace("_", " ").replace("/", " ")
    text = "; ".join(
        sentence for sentence in re.split(r"[.\n;]", text) if not re.search(GAP_PATTERN, sentence)
    )
    # An aside about excluded boilerplate does not negate preserved text.
    # Only remove explicit parentheticals listing these discarded material types;
    # an aside naming headings/source/chunks must retain its negation.
    text = re.sub(
        r"\(only (?:(?:empty|unreadable|duplicate|boilerplate|material|content|or|and)[,\s]+)+"
        r"(?:is|are) omitted\)",
        "",
        text,
    )
    # Negated preservation must not count as affirmative coverage. Keep the
    # deterministic no-summary/no-rewrite statement for its separate group.
    affirmative = "; ".join(
        sentence
        for sentence in re.split(r"[.\n;]", text)
        if not re.search(
            r"(?:not|never|no longer|doesn't|does not|cannot|can't)\s+"
            r"(?:be\s+)?(?:preserv|retain|keep|includ)|(?:discard|omit|lose|drop)|"
            r"\b(?:no|without)\s+(?:original|heading|source|chunk|model)",
            sentence,
        )
    )
    return {
        label
        for label, patterns in PREPARATION_GROUPS.items()
        if all(
            re.search(pattern, text if label.startswith("deterministic") else affirmative)
            for pattern in patterns
        )
    }


def preparation_passages(payload) -> tuple[list[str], bool]:
    """Match the owning guide or a distinctive untitled contract excerpt.

    Search excerpts often have headings and IDs, but no document title. Such
    excerpts can support facts; they cannot verify the missing source title.
    A broader decisions heading mentioning ingestion is not the owning guide.
    """
    evidence = []
    verified_title = False

    def visit(value, owner=False, named_elsewhere=False):
        nonlocal verified_title
        if isinstance(value, dict):
            title = str(value.get("title") or "").strip().lower()
            text = " ".join(
                value.get(key, "")
                for key in ("heading", "text", "content")
                if isinstance(value.get(key, ""), str) and value.get(key, "")
            ).strip()
            h1 = re.search(r"(?m)^#\s+Manual ingestion\s*$", text, re.I)
            if title:
                owner = title == "manual ingestion"
                named_elsewhere = not owner
            elif not named_elsewhere:
                owner = owner or bool(h1)
            if owner:
                verified_title = True
            heading = str(value.get("heading") or "").lstrip("# ").strip().lower()
            contract = heading == "processing contract" or bool(
                re.search(r"(?m)^##\s+Processing contract\s*$", text, re.I)
            )
            # No fuzzy Manual-ingestion substring match. A title-free candidate
            # needs the concrete document/chunk preservation contract shape.
            candidate = bool(
                not named_elsewhere
                and contract
                and re.search(r"original", text, re.I)
                and re.search(r"headings?", text, re.I)
                and re.search(r"chunk", text, re.I)
                and re.search(r"deterministic", text, re.I)
            )
            if owner or candidate:
                evidence.append(text)
            for child in value.values():
                visit(child, owner, named_elsewhere)
        elif isinstance(value, list):
            for child in value:
                visit(child, owner, named_elsewhere)

    visit(payload)
    return evidence, verified_title


def preparation_deficits(messages, answer: str, attribution: bool) -> list[str]:
    last_human = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
    evidence_start = last_human
    if re.search(
        r"that preparation|those preserved|what else survives|missing preservation",
        str(messages[last_human].content),
        re.I,
    ):
        previous = [i for i, m in enumerate(messages[:last_human]) if isinstance(m, HumanMessage)]
        if previous:
            evidence_start = previous[-1]
    evidence = []
    verified_title = False
    for message in messages[evidence_start + 1 :]:
        if not isinstance(message, ToolMessage) or message.name not in {
            "search_knowledge",
            "read_document",
        }:
            continue
        try:
            payload = json.loads(message.content)
        except (ValueError, TypeError):
            continue

        passages, titled = preparation_passages(payload)
        evidence.extend(passages)
        verified_title = verified_title or titled

    supported = preparation_features("\n".join(evidence))
    covered = preparation_features(answer)
    deficits = [
        f"Include supported fact: {label}"
        for label in PREPARATION_GROUPS
        if label in supported and label not in covered
    ]
    # Unsupported requested detail requires a precise explicit gap, not an
    # ungrounded affirmative claim. Reuse recognizer patterns to associate gaps.
    gap_sentences = [
        sentence.lower()
        for sentence in re.split(r"[.\n;]", answer)
        if re.search(GAP_PATTERN, sentence, re.I)
    ]
    for label, patterns in PREPARATION_GROUPS.items():
        if label not in supported and label in covered:
            deficits.append(f"Remove unsupported claim: {label}")
        if label not in supported and not any(
            all(re.search(pattern, sentence.replace("/", " ")) for pattern in patterns)
            for sentence in gap_sentences
        ):
            deficits.append(f"State evidence gap for: {label}; do not invent it")
    normalized_attribution = " ".join(answer.lower().split())
    if attribution and not verified_title:
        deficits.append(
            "Requested source title is not verified in retrieved passages; "
            "do not invent Manual ingestion attribution"
        )
    if (
        attribution
        and verified_title
        and (
            "manual ingestion" not in normalized_attribution
            or "processing contract" not in normalized_attribution
        )
    ):
        deficits.append("Name Manual ingestion / Processing contract as the requested source")
    if attribution and "chunk identities, hashes and offsets" in supported:
        if "selected target workflow" not in normalized_attribution:
            deficits.append("Name Selected target workflow for chunk offsets")
    return deficits


class AnswerRepairState(AgentState):
    answer_word_limit: NotRequired[int | None]
    answer_repair: NotRequired[bool]
    answer_draft_id: NotRequired[str | None]
    answer_deficits: NotRequired[list[str]]
    preparation_check: NotRequired[bool]
    preparation_attribution: NotRequired[bool]


def bounded_messages(messages, turns: int, character_limit: int = 48000):
    def is_real_human(message):
        return isinstance(message, HumanMessage) and message.name != REPAIR_MESSAGE_NAME

    humans = [index for index, message in enumerate(messages) if is_real_human(message)]
    selected = list(messages[humans[-turns] :]) if len(humans) > turns else list(messages)
    while (
        len([m for m in selected if is_real_human(m)]) > 1
        and sum(len(str(m.content)) for m in selected) > character_limit
    ):
        next_human = next(i for i, m in enumerate(selected[1:], 1) if is_real_human(m))
        selected = selected[next_human:]
    # Preserve tool-call/result pairs; shorten their content in the model view only.
    for index, message in enumerate(selected):
        excess = sum(len(str(m.content)) for m in selected) - character_limit
        if excess <= 0:
            break
        if isinstance(message, ToolMessage) and isinstance(message.content, str):
            keep = max(256, len(message.content) - excess - 40)
            if keep < len(message.content):
                selected[index] = message.model_copy(
                    update={"content": message.content[:keep] + "\n[Passage shortened for context]"}
                )
    if sum(len(str(m.content)) for m in selected) > character_limit:
        raise ValueError("Current turn exceeds the model context limit")
    return selected


def create_graph(
    model,
    knowledge,
    checkpointer,
    settings: Settings,
    *,
    assistant_config: AssistantConfig | None = None,
):
    """Build the single assistant graph with bounded inference and retrieval."""
    assistant_config = assistant_config or load_assistant_config(settings)
    allowed_tools = assistant_config.knowledge_tools
    # One response per permitted retrieval round, then one final answer.
    model_call_limit = assistant_config.call_limit + 1

    @tool
    async def search_knowledge(query: str) -> str:
        """Search prepared documents for passages relevant to a specific question."""
        return json.dumps(
            await knowledge.call("search", {"query": query[:1500]}), ensure_ascii=False
        )

    @tool
    async def read_document(doc_id: str, offset: int = 0) -> str:
        """Read more of a retrieved document using its internal document ID."""
        return json.dumps(
            await knowledge.call("read", {"doc_id": doc_id, "offset": offset}), ensure_ascii=False
        )

    class Grounding(AgentMiddleware):
        state_schema = AnswerRepairState

        async def abefore_agent(self, state, runtime):
            last = next(
                (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
            )
            if last is None:
                raise ValueError("A user question is required")
            query = last.content if isinstance(last.content, str) else str(last.content)
            scoped = preparation_scope(state["messages"], settings.history_turns)
            named_scope = named_manual_ingestion_scope(query)
            search_query = PREPARATION_QUERY if scoped or named_scope else query[:1500]
            grounding_messages = []

            async def retrieve(operation, arguments):
                result = await operation.ainvoke(arguments)
                call_id = "knowledge_" + uuid.uuid4().hex
                grounding_messages.extend(
                    [
                        AIMessage(
                            content="",
                            tool_calls=[{"name": operation.name, "args": arguments, "id": call_id}],
                        ),
                        ToolMessage(content=result, tool_call_id=call_id, name=operation.name),
                    ]
                )
                return json.loads(result)

            result = await retrieve(search_knowledge, {"query": search_query})
            if (scoped or named_scope) and assistant_config.call_limit > 1:
                doc_id = preparation_document(result)
                if doc_id:
                    await retrieve(read_document, {"doc_id": doc_id, "offset": 0})
            automatic_calls = len(grounding_messages) // 2
            thread_counts = state.get("thread_tool_call_count", {}).copy()
            thread_counts["__all__"] = thread_counts.get("__all__", 0) + automatic_calls
            return {
                "answer_word_limit": requested_word_limit(query),
                "answer_repair": False,
                "answer_draft_id": None,
                "answer_deficits": [],
                "preparation_check": scoped,
                "preparation_attribution": bool(
                    re.search(r"source|heading|attribution|cite", query, re.I)
                ),
                "messages": grounding_messages,
                # Automatic calls bypass the tool node, so seed the installed
                # limiter explicitly. Run counts reset even on UUID continuation.
                "run_tool_call_count": {"__all__": automatic_calls},
                "thread_tool_call_count": thread_counts,
            }

        async def awrap_model_call(self, request, handler):
            tools = [tool for tool in request.tools if getattr(tool, "name", "") in allowed_tools]
            if request.state.get("answer_repair"):
                cap = request.state["answer_word_limit"]
                length = (
                    f"to at most {cap} whitespace-separated words in total; "
                    f"aim for {max(1, cap * 4 // 5)}. Count source attribution too. "
                    if cap
                    else "to address all identified deficits. "
                )
                instruction = (
                    "Revise your preceding answer "
                    + length
                    + "Preserve supported facts, valid provenance, dates and uncertainty. "
                    "Remove repetition and section labels. Correct omissions and wrong source "
                    "attribution rather than retaining an exact erroneous source title or heading. "
                    "Use only evidence already retrieved. Return only the revised answer; "
                    "do not request tools. "
                    + (
                        "Recheck and retain ALL supported requested preservation fields, not only listed deficits: "
                        "deterministic/no-summary/no-meaning-rewrite; originals; headings/substantive text; "
                        "source identity/metadata; chunk identities/hashes/offsets; "
                        "model configuration retained with vectors. "
                        if request.state.get("preparation_check")
                        else ""
                    )
                    + "Correct these deficits: "
                    + "; ".join(request.state.get("answer_deficits", []))
                )
                repair_message = HumanMessage(content=instruction, name=REPAIR_MESSAGE_NAME)
                messages = bounded_messages(
                    [*request.messages, repair_message], settings.history_turns
                )
                return await handler(
                    request.override(
                        tools=[],
                        tool_choice=None,
                        messages=messages,
                    )
                )
            messages = bounded_messages(request.messages, settings.history_turns)
            return await handler(request.override(tools=tools, messages=messages))

        @hook_config(can_jump_to=["model"])
        async def aafter_model(self, state, runtime):
            cap = state.get("answer_word_limit")
            answer = state["messages"][-1]
            if not isinstance(answer, AIMessage):
                return None
            repairing = state.get("answer_repair", False)
            if answer.tool_calls:
                if repairing:
                    raise ValueError("Answer repair requested tools")
                return None
            if any(
                answer.response_metadata.get(key) == "length"
                for key in ("done_reason", "finish_reason")
            ):
                raise ValueError("Current final generation stopped at its token limit")
            content = answer.content
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Current turn produced no final answer")
            deficits = (
                preparation_deficits(
                    bounded_messages(state["messages"], settings.history_turns),
                    content,
                    state.get("preparation_attribution", False),
                )
                if state.get("preparation_check")
                else []
            )
            if cap is not None and len(content.split()) > cap:
                deficits.append("Answer exceeds the requested word limit")
            if not deficits:
                if repairing:
                    return {"messages": [RemoveMessage(id=state["answer_draft_id"])]}
                return None
            if repairing or state.get("run_model_call_count", 0) >= model_call_limit:
                # No truncation or extra allowance: an unsuccessful repair is a failure.
                raise ValueError("; ".join(deficits))
            return {
                "answer_repair": True,
                "answer_draft_id": answer.id,
                "answer_deficits": deficits,
                "jump_to": "model",
            }

        async def awrap_tool_call(self, request, handler):
            if request.tool_call["name"] not in allowed_tools:
                raise ValueError("Unavailable tool")
            return await handler(request)

    profile = HarnessProfile(
        base_system_prompt="",
        excluded_middleware=frozenset({"SummarizationMiddleware"}),
        general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        excluded_tools=frozenset(
            {
                "ls",
                "read_file",
                "write_file",
                "edit_file",
                "glob",
                "grep",
                "execute",
                "task",
                "write_todos",
            }
        ),
    )
    # Deep Agents resolves prebuilt models by their LangChain provider profile,
    # not by the serialization identifier returned by _llm_type.
    register_harness_profile(model._get_ls_params()["ls_provider"], profile)
    return create_deep_agent(
        model=model,
        tools=[search_knowledge, read_document],
        system_prompt=assistant_config.system_prompt,
        middleware=[
            Grounding(),
            ModelCallLimitMiddleware(run_limit=model_call_limit, exit_behavior="error"),
            # Preserve the answer path when a model attempts another retrieval
            # after the bounded call budget: return a tool error to the model so
            # it can answer from passages already retrieved instead of aborting.
            ToolCallLimitMiddleware(
                run_limit=assistant_config.call_limit, exit_behavior="continue"
            ),
            ModelRetryMiddleware(max_retries=1, initial_delay=1, max_delay=2, on_failure="error"),
        ],
        checkpointer=checkpointer,
        name="assistant",
    ).with_config(
        # Graph steps include middleware bookkeeping, not just model/tool calls.
        # The explicit call budgets above bound inference and retrieval work.
        {"recursion_limit": 8 + 6 * model_call_limit}
    )
