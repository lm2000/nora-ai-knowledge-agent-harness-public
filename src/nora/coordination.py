"""HTTP and AG-UI adapters around the shared Deep Agent graph."""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated

from ag_ui.core import RunAgentInput
from ag_ui.encoder import EventEncoder
from ag_ui_langgraph import LangGraphAgent
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, ConfigDict, Field

from nora.agent import create_graph
from nora.assistant import assistant_thread_id, load_assistant_config
from nora.auth import BearerAuth, BodyLimit
from nora.budget import BudgetExceeded, RequestBudget
from nora.config import Settings, credential
from nora.mcp_client import KnowledgeClient
from nora.ownership import InMemoryOwnershipStore, OwnershipStore, PostgresOwnershipStore
from nora.providers import credential_available
from nora.selector import build_selector

logger = logging.getLogger(__name__)


@dataclass
class Runtime:
    graph: object
    knowledge: object
    provider: str
    ownership: OwnershipStore


def _warn_missing_provider_credentials(models) -> None:
    """Log startup warnings for assistant model candidates lacking a credential.

    The selector skips these candidates per request; the one-shot startup
    warning makes the misconfiguration visible before the first request.
    Credential names are logged, never values.
    """
    missing = [spec for spec in models if not credential_available(spec)]
    for spec in missing:
        logger.warning(
            "Assistant model %s/%s has no configured provider credential (%s); "
            "the selector will skip it until configured",
            spec.provider,
            spec.model,
            spec.token_name,
        )
    if models and len(missing) == len(models):
        logger.warning(
            "Assistant has no model with a configured provider credential; "
            "requests will fail until one is configured",
        )


@asynccontextmanager
async def production_runtime(settings: Settings):
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.conninfo import make_conninfo

    conninfo = make_conninfo(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        dbname=settings.postgres_db,
        password=credential("POSTGRES_PASSWORD"),
    )
    knowledge = KnowledgeClient(
        settings.retrieval_url, credential("MCP_TOKEN"), settings.tool_timeout
    )
    assistant_config = load_assistant_config(settings)
    _warn_missing_provider_credentials(assistant_config.models)
    async with AsyncPostgresSaver.from_conn_string(conninfo) as saver:
        await saver.setup()
        model = build_selector(
            assistant_config.models,
            timeout=settings.request_timeout,
            cost_weight=settings.selector_cost_weight,
            latency_weight=settings.selector_latency_weight,
            log_path=settings.selector_log_path,
        )
        provider = "assistant-selector"
        ownership = PostgresOwnershipStore(conninfo)
        await ownership.setup()
        graph = create_graph(model, knowledge, saver, settings, assistant_config=assistant_config)
        yield Runtime(graph, knowledge, provider, ownership)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    thread_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    model_config = ConfigDict(extra="forbid")


def create_app(
    settings: Settings | None = None,
    runtime: Runtime | None = None,
    *,
    token: str | None = None,
    runtime_factory=production_runtime,
):
    settings = settings or Settings.from_env()
    token = credential("INTERNAL_TOKEN") if token is None else token
    semaphore = asyncio.Semaphore(settings.concurrency)
    mcp = FastMCP("Nora Intelligence System", mask_error_details=True)
    mcp_app = mcp.http_app(path="/", stateless_http=True, json_response=True)

    @asynccontextmanager
    async def lifespan(app):
        app.state.budget = RequestBudget(
            settings.state_dir / "requests.sqlite3", settings.daily_limit
        )
        if runtime is not None:
            app.state.runtime = runtime
            app.state.ownership = runtime.ownership or InMemoryOwnershipStore()
            async with mcp_app.lifespan(mcp_app):
                yield
        else:
            async with runtime_factory(settings) as built:
                app.state.runtime = built
                app.state.ownership = built.ownership
                async with mcp_app.lifespan(mcp_app):
                    yield

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(BodyLimit)
    app.add_middleware(BearerAuth, token=token)
    app.mount("/mcp", mcp_app)

    async def _require_owner(thread_id: uuid.UUID):
        accepted, _ = await app.state.ownership.claim(str(thread_id))
        if not accepted:
            raise HTTPException(403, "Conversation is unavailable.")

    async def take_slot():
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=settings.request_timeout)
        except TimeoutError as error:
            raise HTTPException(503, "Nora is busy. Please retry.") from error
        try:
            await asyncio.to_thread(app.state.budget.take)
        except BudgetExceeded as error:
            semaphore.release()
            raise HTTPException(429, "Daily request limit reached. Try again tomorrow.") from error
        except BaseException:
            semaphore.release()
            raise

    @app.get("/health")
    async def health():
        try:
            state = await app.state.runtime.knowledge.health()
            if not state.get("ready"):
                raise RuntimeError("Retrieval is not ready")
            return {
                "status": "ok",
                "agent": "assistant",
                "provider": app.state.runtime.provider,
                "documents": state.get("documents", 0),
                "points": state.get("points", 0),
            }
        except Exception:
            return JSONResponse({"status": "starting"}, status_code=503)

    async def ask_operation(data: Question):
        """Shared in-process operation for the JSON and MCP entrances."""
        await _require_owner(data.thread_id)
        if not data.question.strip() or len(data.question) > settings.question_limit:
            raise HTTPException(422, "Please provide a shorter, nonempty question")
        await take_slot()
        try:
            async with (
                app.state.runtime.knowledge.pinned(),
                asyncio.timeout(settings.request_timeout),
            ):
                effective_thread_id = assistant_thread_id(str(data.thread_id))
                result = await app.state.runtime.graph.ainvoke(
                    {"messages": [HumanMessage(content=data.question)]},
                    {
                        "configurable": {"thread_id": effective_thread_id},
                    },
                )
                last = max(
                    i for i, m in enumerate(result["messages"]) if isinstance(m, HumanMessage)
                )
                answer = next(
                    (
                        m.content
                        for m in reversed(result["messages"][last + 1 :])
                        if isinstance(m, AIMessage) and m.content and not m.tool_calls
                    ),
                    "",
                )
                if not str(answer).strip():
                    # A provider can exhaust its output budget without raising.
                    # Never publish an empty success or reuse a prior turn's answer.
                    raise RuntimeError("Current turn produced no final answer")
                return {
                    "answer": answer,
                    "thread_id": str(data.thread_id),
                    "role": "assistant",
                    "knowledge_calls": sum(
                        isinstance(m, ToolMessage) for m in result["messages"][last:]
                    ),
                }
        except TimeoutError as error:
            raise HTTPException(504, "Request timed out. Please retry.") from error
        except Exception as error:
            raise HTTPException(
                503, "Nora could not complete this request. Please retry."
            ) from error
        finally:
            semaphore.release()

    @app.post("/ask")
    async def ask(data: Question):
        return await ask_operation(data)

    @mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        }
    )
    async def ask_nis(
        question: Annotated[str, Field(min_length=1, max_length=4000)],
        thread_id: uuid.UUID | None = None,
    ) -> dict:
        """Ask NIS about saved knowledge, comparisons or interview material.

        Omit thread_id to start a new conversation. Reuse the returned UUID for
        a follow-up. NIS saves the conversation and chooses its own model.
        """
        try:
            result = await ask_operation(
                Question(question=question, thread_id=thread_id or uuid.uuid4())
            )
        except HTTPException as error:
            # Only curated application errors reach clients, never provider details.
            raise ToolError(f"NIS request failed ({error.status_code}): {error.detail}") from None
        return {"answer": result["answer"], "thread_id": result["thread_id"]}

    @app.get("/history/{thread_id}")
    async def history(thread_id: uuid.UUID):
        await _require_owner(thread_id)
        try:
            state = await app.state.runtime.graph.aget_state(
                {"configurable": {"thread_id": assistant_thread_id(str(thread_id))}}
            )
        except Exception as error:
            raise HTTPException(
                503, "Conversation history is unavailable. Please retry."
            ) from error
        return {
            "messages": [
                {
                    "id": m.id,
                    "role": "user" if isinstance(m, HumanMessage) else "assistant",
                    "content": m.content,
                }
                for m in state.values.get("messages", [])
                if isinstance(m, (HumanMessage, AIMessage))
                and m.content
                and not getattr(m, "tool_calls", None)
            ]
        }

    @app.post("/agent")
    async def agent(data: RunAgentInput, request: Request):
        if len(data.messages) > 40 or len(data.model_dump_json().encode()) > 70000:
            raise HTTPException(413, "Conversation too large. Start a new conversation.")
        if not any(getattr(m, "role", "") == "user" for m in data.messages):
            raise HTTPException(422, "A user question is required")
        if any(
            getattr(m, "role", "") == "user"
            and len(str(getattr(m, "content", ""))) > settings.question_limit
            for m in data.messages
        ):
            raise HTTPException(413, "Please shorten the question")
        try:
            uuid.UUID(data.thread_id)
        except ValueError as error:
            raise HTTPException(400, "Invalid conversation") from error
        if request.headers.get("X-Nora-Role") is not None:
            raise HTTPException(422, "Role selection is unsupported.")
        thread_uuid = uuid.UUID(data.thread_id)
        await _require_owner(thread_uuid)
        encoder = EventEncoder(accept=request.headers.get("accept"))
        await take_slot()  # Budget errors become HTTP 429 before streaming headers.

        effective_thread_id = assistant_thread_id(str(data.thread_id))

        async def events():
            adapter = LangGraphAgent(
                name="assistant",
                graph=app.state.runtime.graph,
                config={
                    "configurable": {"thread_id": effective_thread_id},
                },
                emit_raw_events=False,
            )
            queue: asyncio.Queue = asyncio.Queue()

            async def producer():
                try:
                    async with (
                        app.state.runtime.knowledge.pinned(),
                        asyncio.timeout(settings.request_timeout),
                    ):
                        # The adapter replaces config.thread_id with the input id.
                        # Use our checkpoint namespace and restore public event IDs.
                        agent_input = data.model_copy(update={"thread_id": effective_thread_id})
                        async for event in adapter.run(agent_input):
                            event_type = getattr(event.type, "value", str(event.type))
                            # Knowledge tools execute entirely on the server. Keep
                            # their overlapping provider deltas out of the plain
                            # answer UI; graph execution and checkpoints retain them.
                            if event_type.startswith(("REASONING", "TOOL_CALL_")):
                                continue
                            if getattr(event, "thread_id", None) == effective_thread_id:
                                event = event.model_copy(update={"thread_id": data.thread_id})
                            await queue.put(encoder.encode(event))
                except Exception:
                    # Errors are surfaced by the lack of further events; the
                    # client will see a truncated stream and can retry.
                    pass
                finally:
                    await queue.put(None)

            task = asyncio.create_task(producer())

            def release_semaphore(_):
                try:
                    semaphore.release()
                except RuntimeError:
                    pass

            task.add_done_callback(release_semaphore)
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    yield item
            except asyncio.CancelledError:
                # Keep the producer running so the graph can finish and persist
                # state even if the client disconnects or starts another conversation.
                pass

        return StreamingResponse(events(), media_type=encoder.get_content_type())

    return app
