#!/usr/bin/env python3
"""Run isolated single-assistant browser acceptance with synthetic model/retrieval.

Run from the repository root: mise exec -- python scripts/ui_acceptance.py.
Requires Playwright and Chromium; NIS_BROWSER_EXECUTABLE may point to Chrome.
No inference credentials, live services or private corpus are used.
"""

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

CHECKOUT = Path(__file__).resolve().parents[1]
PYTHON = os.environ.get("NORA_UI_PYTHON", sys.executable)
PNPM = os.environ.get("NORA_UI_PNPM", "pnpm")


class HarnessError(Exception):
    pass


def free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def poll_url(url: str, timeout: float = 30.0, headers: dict[str, str] | None = None) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=1.0, headers=headers)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def write_child_server(path: Path, checkout: Path, port: int, token: str, state_dir: Path) -> None:
    path.write_text(
        textwrap.dedent(
            f"""
            import os
            import sys

            sys.path.insert(0, {str(checkout / "src")!r})

            os.environ["NORA_STATE_DIR"] = {str(state_dir)!r}
            os.environ["NORA_DATA_DIR"] = {str(state_dir / "data")!r}
            os.environ["NORA_RELEASES_ROOT"] = {str(state_dir / "releases")!r}
            os.environ["NORA_CONCURRENCY"] = "10"

            from langchain_core.language_models import BaseChatModel
            from langchain_core.messages import AIMessage, HumanMessage
            from langchain_core.outputs import ChatGeneration, ChatResult
            from langgraph.checkpoint.memory import InMemorySaver
            import uvicorn

            from nora.agent import create_graph
            from nora.config import Settings
            from nora.coordination import Runtime, create_app
            from nora.ownership import InMemoryOwnershipStore
            from nora.assistant import load_assistant_config


            class FakeKnowledge:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    pass
                def pinned(self):
                    return self
                async def call(self, name, arguments):
                    return {{"results": [{{"doc_id": "synthetic", "text": "Synthetic knowledge."}}]}}
                async def health(self):
                    return {{"ready": True, "documents": 3, "points": 7}}

            class AssistantModel(BaseChatModel):
                @property
                def _llm_type(self):
                    return "synthetic-assistant"
                def bind_tools(self, tools, **kwargs):
                    return self
                def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                    questions = [str(m.content) for m in messages if isinstance(m, HumanMessage)]
                    topic = "cedar" if any("cedar" in q for q in questions) else "maple"
                    answer = "Synthetic answer: " + topic + "; questions=" + str(len(questions))
                    return ChatResult(generations=[ChatGeneration(message=AIMessage(content=answer))])
                async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
                    return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

            settings = Settings.from_env()
            config = load_assistant_config(settings)
            model = AssistantModel()
            knowledge = FakeKnowledge()
            graph = create_graph(model, knowledge, InMemorySaver(), settings, assistant_config=config)
            runtime = Runtime(graph, knowledge, "synthetic", InMemoryOwnershipStore())
            app = create_app(settings, runtime=runtime, token={token!r})
            uvicorn.run(app, host="127.0.0.1", port={port}, log_level="warning")
            """
        ),
        encoding="utf-8",
    )


@dataclass
class Ports:
    backend: int
    frontend: int


@dataclass
class Result:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def ok(self, name: str, detail: str | None = None):
        self.passed.append(name)
        if detail is not None:
            self.details[name] = detail

    def fail(self, name: str, detail: str | None = None):
        self.failed.append(name)
        if detail is not None:
            self.details[name] = detail


def start_backend(ports: Ports, token: str, state_dir: Path, log_dir: Path):
    script = log_dir / "assistant_server.py"
    write_child_server(script, CHECKOUT, ports.backend, token, state_dir)
    with (log_dir / "assistant.log").open("wb") as log:
        proc = subprocess.Popen(
            [PYTHON, str(script)],
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=CHECKOUT,
            start_new_session=True,
        )
    if not poll_url(
        f"http://127.0.0.1:{ports.backend}/health", headers={"Authorization": f"Bearer {token}"}
    ):
        stop_backends({"assistant": proc})
        raise HarnessError("Synthetic assistant did not start")
    return {"assistant": proc}


def stop_backends(procs: dict[str, subprocess.Popen], timeout: float = 10.0):
    for proc in procs.values():
        try:
            if proc.poll() is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                proc.kill()
            proc.wait(timeout=5.0)
        except ProcessLookupError:
            pass
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=5.0)
            except Exception:
                pass


def start_frontend(ports: Ports, token: str, log_dir: Path) -> subprocess.Popen:
    env = os.environ.copy()
    env.update(
        {
            "PORT": str(ports.frontend),
            "NORA_COORDINATION_URL": f"http://127.0.0.1:{ports.backend}",
            "NORA_INTERNAL_TOKEN": token,
            "NORA_UI_ALLOWED_ORIGINS": (
                f"http://127.0.0.1:{ports.frontend},http://localhost:{ports.frontend}"
            ),
            "NEXT_TELEMETRY_DISABLED": "1",
            "COPILOTKIT_TELEMETRY_DISABLED": "true",
        }
    )
    build_log = (log_dir / "frontend_build.log").open("wb")
    build = subprocess.run(
        [PNPM, "--dir", "ui", "run", "build"],
        env=env,
        cwd=CHECKOUT,
        stdout=build_log,
        stderr=subprocess.STDOUT,
    )
    if build.returncode != 0:
        raise HarnessError(f"UI build failed (exit {build.returncode}); see {build_log.name}")
    server_log = (log_dir / "frontend_server.log").open("wb")
    proc = subprocess.Popen(
        [PNPM, "--dir", "ui", "run", "start"],
        env=env,
        cwd=CHECKOUT,
        stdout=server_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    if not poll_url(f"http://127.0.0.1:{ports.frontend}", timeout=60.0):
        raise HarnessError(f"Frontend did not start on port {ports.frontend}")
    return proc


def stop_frontend(proc: subprocess.Popen | None, timeout: float = 15.0):
    if proc is None:
        return
    try:
        if proc.poll() is None:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            proc.kill()
        proc.wait(timeout=5.0)
    except ProcessLookupError:
        pass
    except Exception:
        try:
            proc.kill()
            proc.wait(timeout=5.0)
        except Exception:
            pass


def run_browser_tests(base: str, ports: Ports, token: str, verify_dir: Path, result: Result):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as pw:
        launch = {"headless": True}
        if os.environ.get("NIS_BROWSER_EXECUTABLE"):
            launch["executable_path"] = os.environ["NIS_BROWSER_EXECUTABLE"]
        with pw.chromium.launch(**launch) as browser:
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base)
            expect(page.get_by_role("status")).to_contain_text("3 prepared documents")
            assert page.get_by_role("combobox").count() == 0
            result.ok("single-assistant-interface")

            def thread():
                return page.evaluate('localStorage.getItem("nis-assistant-thread")')

            def send(text, expected):
                messages = page.locator('[data-testid="copilot-assistant-message"]')
                page.locator('[data-testid="copilot-chat-textarea"]').fill(text)
                button = page.locator('[data-testid="copilot-send-button"]')
                expect(button).to_be_enabled()
                button.click()
                expect(messages.last).to_contain_text(expected, timeout=20000)

            send("My topic is cedar", "cedar; questions=1")
            first = thread()
            send("What was my topic?", "cedar; questions=2")
            result.ok("context-follow-up", first)
            page.reload()
            expect(page.locator('[data-testid="copilot-assistant-message"]').last).to_contain_text(
                "cedar; questions=2", timeout=20000
            )
            assert thread() == first
            result.ok("reload-restores-history", first)
            page.get_by_role("button", name="New conversation").click()
            second = thread()
            assert second and second != first
            send("My topic is maple", "maple; questions=1")
            result.ok("separate-topic-new-chat", second)
            page.evaluate("id => localStorage.setItem('nis-assistant-thread', id)", first)
            page.reload()
            expect(page.locator('[data-testid="copilot-assistant-message"]').last).to_contain_text(
                "cedar; questions=2", timeout=20000
            )
            result.ok("resume-prior-assistant-chat")
            history = page.request.get(base + "/api/history/" + first)
            assert history.ok and "cedar" in history.text()
            result.ok("uuid-history-route")
            for path in [
                "/api/transfer",
                "/api/history/knowledge/" + first,
                "/api/copilotkit/assistant/info",
                "/api/copilotkit/agent/knowledge/connect",
            ]:
                assert page.request.get(base + path).status == 404, path
            result.ok("removed-role-interfaces-rejected")
            assert not errors, errors
            result.ok("no-browser-errors")
            page.screenshot(path=str(verify_dir / "assistant.png"))


def main() -> int:
    verify_dir = (
        CHECKOUT
        / ".verification"
        / f"ui-acceptance-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    )
    verify_dir.mkdir(parents=True, exist_ok=True)

    result = Result()
    backend_procs: dict[str, subprocess.Popen] = {}
    frontend_proc: subprocess.Popen | None = None
    state_dir = Path(tempfile.mkdtemp(prefix="nora-ui-state-"))
    token = f"ui-acceptance-{uuid.uuid4().hex}"

    try:
        ports = Ports(
            backend=free_port(),
            frontend=free_port(),
        )
        result.details["ports"] = {
            "backend": ports.backend,
            "frontend": ports.frontend,
        }

        backend_procs = start_backend(ports, token, state_dir, verify_dir)
        frontend_proc = start_frontend(ports, token, verify_dir)
        base = f"http://127.0.0.1:{ports.frontend}"
        run_browser_tests(base, ports, token, verify_dir, result)
    except Exception as error:
        result.fail("harness-error", f"{type(error).__name__}: {error}")
        traceback.print_exc()
    finally:
        stop_frontend(frontend_proc)
        stop_backends(backend_procs)
        shutil.rmtree(state_dir, ignore_errors=True)

    outcome = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base": str(base) if "base" in locals() else None,
        "passed": result.passed,
        "failed": result.failed,
        "details": result.details,
    }
    (verify_dir / "ui-acceptance-result.json").write_text(
        json.dumps(outcome, indent=2), encoding="utf-8"
    )

    print(json.dumps(outcome, indent=2))
    if result.failed:
        print(f"FAILED checks: {len(result.failed)}", file=sys.stderr)
        return len(result.failed)
    print("All UI acceptance checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
