"""HTTP and AG-UI adapters around the shared Deep Agent graph."""

import asyncio
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass

from ag_ui.core import RunAgentInput
from ag_ui.encoder import EventEncoder
from ag_ui_langgraph import LangGraphAgent
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field

from nora.agent import create_graph
from nora.auth import BearerAuth, BodyLimit
from nora.budget import BudgetExceeded, RequestBudget
from nora.config import Settings, credential
from nora.mcp_client import KnowledgeClient
from nora.ownership import InMemoryOwnershipStore, OwnershipStore, PostgresOwnershipStore
from nora.roles import load_role_config, role_thread_id, valid_role
from nora.selector import build_selector


@dataclass
class Runtime:
    graph: object
    knowledge: object
    role: str
    provider: str
    ownership: OwnershipStore


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
    role_config = load_role_config(settings.role, settings)
    async with AsyncPostgresSaver.from_conn_string(conninfo) as saver:
        await saver.setup()
        if role_config.models:
            model = build_selector(
                role_config.models,
                timeout=settings.request_timeout,
                cost_weight=settings.selector_cost_weight,
                latency_weight=settings.selector_latency_weight,
                log_path=settings.selector_log_path,
            )
            provider = "role-selector"
        else:
            # Backward-compatible single-provider path for tests/legacy callers.
            from nora.routing import build_model as legacy_build_model

            model = legacy_build_model(settings)
            provider = "routed-ollama" if model._llm_type == "nora-router" else "ollama"
        ownership = PostgresOwnershipStore(conninfo)
        await ownership.setup()
        graph = create_graph(model, knowledge, saver, settings, role_config=role_config)
        yield Runtime(graph, knowledge, settings.role, provider, ownership)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    thread_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    role: str | None = None


class TransferRequest(BaseModel):
    source_role: str
    source_thread_id: uuid.UUID
    target_role: str
    target_thread_id: uuid.UUID
    message_ids: list[str] = Field(default_factory=list)


def create_app(
    settings: Settings | None = None,
    runtime: Runtime | None = None,
    *,
    token: str | None = None,
    runtime_factory=production_runtime,
):
    settings = settings or Settings.from_env()
    if runtime is not None:
        from dataclasses import replace

        settings = replace(settings, role=runtime.role)
    token = credential("INTERNAL_TOKEN") if token is None else token
    semaphore = asyncio.Semaphore(settings.concurrency)

    @asynccontextmanager
    async def lifespan(app):
        app.state.budget = RequestBudget(
            settings.state_dir / "requests.sqlite3", settings.daily_limit
        )
        if runtime is not None:
            app.state.runtime = runtime
            app.state.ownership = runtime.ownership or InMemoryOwnershipStore()
            yield
        else:
            async with runtime_factory(settings) as built:
                app.state.runtime = built
                app.state.ownership = built.ownership
                yield

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(BodyLimit)
    app.add_middleware(BearerAuth, token=token)

    def _assert_role(requested: str | None) -> str:
        """Return the effective role, rejecting cross-role requests."""
        effective = requested or settings.role
        if not valid_role(effective):
            raise HTTPException(400, f"Invalid role: {effective}")
        if requested and requested != settings.role:
            # Do not reveal which role this runtime serves or which role owns the thread.
            raise HTTPException(
                403,
                "Thread is not available on this role runtime.",
            )
        return effective

    def _namespaced(thread_id: uuid.UUID | str, role: str) -> str:
        return role_thread_id(role, str(thread_id))

    async def _get_graph_state(thread_id: uuid.UUID | str, role: str):
        """Load graph state, preferring the role-namespaced id.

        Falls back to the legacy un-namespaced id when the namespaced checkpoint
        has no messages.  The AG-UI LangGraphAgent adapter currently persists
        runs under the raw client thread id, while the /ask endpoint uses the
        namespaced id; both must be resumable through /history.
        """
        namespaced = _namespaced(thread_id, role)
        namespaced_state = None
        try:
            async with asyncio.timeout(settings.tool_timeout):
                namespaced_state = await app.state.runtime.graph.aget_state(
                    {"configurable": {"thread_id": namespaced}}
                )
            if namespaced_state.values.get("messages"):
                return namespaced_state
        except Exception:
            pass
        legacy_id = str(thread_id)
        try:
            async with asyncio.timeout(settings.tool_timeout):
                return await app.state.runtime.graph.aget_state(
                    {"configurable": {"thread_id": legacy_id}}
                )
        except Exception:
            # If the namespaced lookup also failed, surface that error.
            if namespaced_state is None:
                raise
            return namespaced_state

    async def _resolve_thread_id(thread_id: uuid.UUID | str, role: str) -> str:
        """Return the effective checkpoint id for a turn or resume.

        Prefer the role-namespaced id.  Fall back to the legacy un-namespaced
        checkpoint when it already holds messages and the namespaced checkpoint
        is empty, so both /ask and AG-UI /agent runs can be resumed.
        """
        namespaced = _namespaced(thread_id, role)
        try:
            async with asyncio.timeout(settings.tool_timeout):
                state = await app.state.runtime.graph.aget_state(
                    {"configurable": {"thread_id": namespaced}}
                )
            if state.values.get("messages"):
                return namespaced
        except Exception:
            pass
        try:
            async with asyncio.timeout(settings.tool_timeout):
                state = await app.state.runtime.graph.aget_state(
                    {"configurable": {"thread_id": str(thread_id)}}
                )
            if state.values.get("messages"):
                return str(thread_id)
        except Exception:
            pass
        return namespaced

    async def _require_owner(thread_id: uuid.UUID, role: str) -> str:
        """Claim or verify ownership of the client-visible thread id for role.

        Raises 403 when the id is already owned by a different role.
        """
        accepted, owner = await app.state.ownership.claim(str(thread_id), role)
        if not accepted:
            # Do not reveal which role owns the thread to a different-role caller.
            raise HTTPException(
                403,
                f"Thread {thread_id} is not available on this role runtime.",
            )
        return owner

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
                "agent": app.state.runtime.role,
                "provider": app.state.runtime.provider,
                "documents": state.get("documents", 0),
                "points": state.get("points", 0),
            }
        except Exception:
            return JSONResponse({"status": "starting"}, status_code=503)

    @app.post("/ask")
    async def ask(data: Question):
        role = _assert_role(data.role)
        await _require_owner(data.thread_id, role)
        if not data.question.strip() or len(data.question) > settings.question_limit:
            raise HTTPException(422, "Please provide a shorter, nonempty question")
        await take_slot()
        try:
            async with (
                app.state.runtime.knowledge.pinned(),
                asyncio.timeout(settings.request_timeout),
            ):
                effective_thread_id = await _resolve_thread_id(data.thread_id, role)
                result = await app.state.runtime.graph.ainvoke(
                    {"messages": [HumanMessage(content=data.question)]},
                    {
                        "configurable": {"thread_id": effective_thread_id},
                        "recursion_limit": 10,
                    },
                )
                answer = next(
                    (
                        m.content
                        for m in reversed(result["messages"])
                        if isinstance(m, AIMessage) and m.content and not m.tool_calls
                    ),
                    "",
                )
                last = max(
                    i for i, m in enumerate(result["messages"]) if isinstance(m, HumanMessage)
                )
                return {
                    "answer": answer,
                    "thread_id": str(data.thread_id),
                    "role": role,
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

    @app.get("/history/{thread_id}")
    async def history_alias(thread_id: uuid.UUID):
        """Backward-compatible history endpoint: uses this runtime's role."""
        return await _history(settings.role, thread_id)

    @app.get("/history/{role}/{thread_id}")
    async def history(role: str, thread_id: uuid.UUID):
        return await _history(role, thread_id)

    async def _history(role: str, thread_id: uuid.UUID):
        _assert_role(role)
        await _require_owner(thread_id, role)
        try:
            state = await _get_graph_state(thread_id, role)
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

    @app.post("/transfer")
    async def transfer(data: TransferRequest):
        """Return a user-reviewable summary of selected source messages.

        The summary is handed to the client; the target role only receives it
        when the user posts it as the first message of a new target thread.
        """
        if data.source_role == data.target_role:
            raise HTTPException(400, "Source and target role must differ")
        if not valid_role(data.source_role) or not valid_role(data.target_role):
            raise HTTPException(400, "Invalid source or target role")
        source_accepted, source_owner = await app.state.ownership.claim(
            str(data.source_thread_id), data.source_role
        )
        if not source_accepted:
            raise HTTPException(
                403,
                f"Source thread is owned by role '{source_owner}', not '{data.source_role}'.",
            )
        try:
            state = await _get_graph_state(data.source_thread_id, data.source_role)
        except Exception as error:
            raise HTTPException(503, "Source conversation is unavailable.") from error
        messages = [
            m
            for m in state.values.get("messages", [])
            if isinstance(m, (HumanMessage, AIMessage))
            and m.content
            and not getattr(m, "tool_calls", None)
        ]
        if data.message_ids:
            messages = [m for m in messages if getattr(m, "id", "") in set(data.message_ids)]
        if not messages:
            raise HTTPException(404, "No transferable messages found")
        # Produce a concise, reviewable summary. It is deterministic text, not a
        # hidden checkpoint dump; the user sees it before confirming transfer.
        lines = [f"Summary from {data.source_role} conversation:"]
        total = 0
        cap = 2400
        for m in messages:
            prefix = "User:" if isinstance(m, HumanMessage) else "Assistant:"
            text = f"{prefix} {m.content}"
            if total + len(text) > cap:
                text = text[: cap - total - 3] + "..."
            lines.append(text)
            total += len(text)
            if total >= cap:
                break
        return {
            "summary": "\n\n".join(lines),
            "source_role": data.source_role,
            "source_thread_id": str(data.source_thread_id),
            "target_role": data.target_role,
            "target_thread_id": str(data.target_thread_id),
            "message_count": len(messages),
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
        role = settings.role
        header_role = request.headers.get("X-Nora-Role")
        if header_role:
            role = _assert_role(header_role)
        thread_uuid = uuid.UUID(data.thread_id)
        await _require_owner(thread_uuid, role)
        encoder = EventEncoder(accept=request.headers.get("accept"))
        await take_slot()  # Budget errors become HTTP 429 before streaming headers.

        effective_thread_id = await _resolve_thread_id(data.thread_id, role)

        async def events():
            adapter = LangGraphAgent(
                name=role,
                graph=app.state.runtime.graph,
                config={
                    "configurable": {"thread_id": effective_thread_id},
                    "recursion_limit": 10,
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
                        async for event in adapter.run(data):
                            event_type = getattr(event.type, "value", str(event.type))
                            # Knowledge tools execute entirely on the server. Keep
                            # their overlapping provider deltas out of the plain
                            # answer UI; graph execution and checkpoints retain them.
                            if event_type.startswith(("REASONING", "TOOL_CALL_")):
                                continue
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
                # state even if the client disconnects or switches roles.
                pass

        return StreamingResponse(events(), media_type=encoder.get_content_type())

    return app
