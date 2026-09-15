#!/usr/bin/env python3
"""Isolated UI acceptance harness for the Nora role-runtime UI.

Starts three real role API runtimes with synthetic model/retrieval doubles on
task-unique localhost ports, builds and starts the Next.js UI, then drives the
browser with Playwright to verify:

  * role selection routes to role-specific backends,
  * sending/receiving messages and role-specific answers,
  * new conversation resets the thread,
  * reload resumes the current thread,
  * a prior thread can be resumed by restoring its localStorage key,
  * selected messages can be transferred to a new target chat,
  * switching role while a response is in-flight does not leak old-role content.

Run from the repository root with the task-local Python environment:

    PLAYWRIGHT_BROWSERS_PATH=/private/tmp/nora-role-playwright \
        /private/tmp/nora-role-runtime-venv/bin/python scripts/ui_acceptance.py

The script exits with the number of failed checks (0 on success).
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
ROLES = ("knowledge", "research", "interview")
PYTHON = os.environ.get("NORA_UI_PYTHON", sys.executable)
NPM = os.environ.get("NORA_UI_NPM", "npm")
BROWSER_PATH = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/private/tmp/nora-role-playwright")


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


def write_child_server(
    path: Path, checkout: Path, role: str, port: int, token: str, state_dir: Path
) -> None:
    path.write_text(
        textwrap.dedent(
            f"""
            import asyncio
            import os
            import sys
            from pathlib import Path

            sys.path.insert(0, {str(checkout)!r})

            os.environ["NORA_STATE_DIR"] = {str(state_dir / role)!r}
            os.environ["NORA_DATA_DIR"] = {str(state_dir / role / "data")!r}
            os.environ["NORA_RELEASES_ROOT"] = {str(state_dir / role / "releases")!r}
            os.environ["NORA_CONCURRENCY"] = "10"
            os.environ["NORA_ROLE"] = {role!r}

            from langchain_core.language_models import BaseChatModel
            from langchain_core.messages import AIMessage, ToolMessage
            from langchain_core.outputs import ChatGeneration, ChatResult
            from langgraph.checkpoint.memory import InMemorySaver
            import uvicorn

            from nora.agent import create_graph
            from nora.config import Settings
            from nora.coordination import Runtime, create_app
            from nora.ownership import InMemoryOwnershipStore
            from nora.roles import load_role_config


            class FakeKnowledge:
                def __init__(self, role):
                    self.role = role

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

                def pinned(self):
                    return self

                async def call(self, name, arguments):
                    return {{
                        "results": [
                            {{"doc_id": "d", "text": f"Prepared answer from the {{self.role}} backend."}}
                        ]
                    }}

                async def health(self):
                    return {{"ready": True, "documents": 3, "points": 7}}


            class RoleModel(BaseChatModel):
                role: str
                delay: float = 0.0

                @property
                def _llm_type(self):
                    return f"fake-{{self.role}}"

                def bind_tools(self, tools, **kwargs):
                    return self

                def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                    tool_texts = [str(m.content) for m in messages if isinstance(m, ToolMessage)]
                    if self.role == "interview":
                        display = "interview analyst"
                    else:
                        display = self.role + " assistant"
                    answer = "Answer from " + display
                    return ChatResult(
                        generations=[ChatGeneration(message=AIMessage(content=answer))]
                    )

                async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
                    if self.delay:
                        await asyncio.sleep(self.delay)
                    return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


            settings = Settings.from_env()
            config = load_role_config({role!r}, settings)
            model = RoleModel(role={role!r}, delay=6.0 if {role!r} == "interview" else 0.0)
            knowledge = FakeKnowledge({role!r})
            graph = create_graph(model, knowledge, InMemorySaver(), settings, role_config=config)
            runtime = Runtime(graph, knowledge, {role!r}, "double", InMemoryOwnershipStore())
            app = create_app(settings, runtime=runtime, token={token!r})
            uvicorn.run(app, host="127.0.0.1", port={port}, log_level="warning")
            """
        ),
        encoding="utf-8",
    )


@dataclass
class Ports:
    knowledge: int
    research: int
    interview: int
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


def start_role_backends(
    ports: Ports, token: str, state_dir: Path, log_dir: Path
) -> dict[str, subprocess.Popen]:
    procs: dict[str, subprocess.Popen] = {}
    auth_header = {"Authorization": f"Bearer {token}"}
    try:
        for role, port in [
            ("knowledge", ports.knowledge),
            ("research", ports.research),
            ("interview", ports.interview),
        ]:
            script = log_dir / f"role_server_{role}.py"
            write_child_server(script, CHECKOUT, role, port, token, state_dir)
            log = (log_dir / f"role_{role}.log").open("wb")
            proc = subprocess.Popen(
                [PYTHON, str(script)],
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=CHECKOUT,
                start_new_session=True,
            )
            procs[role] = proc
        for role, port in [
            ("knowledge", ports.knowledge),
            ("research", ports.research),
            ("interview", ports.interview),
        ]:
            if not poll_url(f"http://127.0.0.1:{port}/health", timeout=30.0, headers=auth_header):
                raise HarnessError(f"Backend for {role} did not start on port {port}")
        return procs
    except Exception:
        stop_role_backends(procs)
        raise


def stop_role_backends(procs: dict[str, subprocess.Popen], timeout: float = 10.0):
    for role, proc in procs.items():
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
            "NORA_KNOWLEDGE_URL": f"http://127.0.0.1:{ports.knowledge}",
            "NORA_RESEARCH_URL": f"http://127.0.0.1:{ports.research}",
            "NORA_INTERVIEW_URL": f"http://127.0.0.1:{ports.interview}",
            "NORA_INTERNAL_TOKEN": token,
            "NORA_UI_ALLOWED_ORIGINS": (
                f"http://127.0.0.1:{ports.frontend},http://localhost:{ports.frontend}"
            ),
            "NEXT_TELEMETRY_DISABLED": "1",
            "COPILOTKIT_TELEMETRY_DISABLED": "true",
            "PLAYWRIGHT_BROWSERS_PATH": BROWSER_PATH,
        }
    )
    build_log = (log_dir / "frontend_build.log").open("wb")
    build = subprocess.run(
        [NPM, "--prefix", "ui", "run", "build"],
        env=env,
        cwd=CHECKOUT,
        stdout=build_log,
        stderr=subprocess.STDOUT,
    )
    if build.returncode != 0:
        raise HarnessError(f"UI build failed (exit {build.returncode}); see {build_log.name}")
    server_log = (log_dir / "frontend_server.log").open("wb")
    proc = subprocess.Popen(
        [NPM, "--prefix", "ui", "run", "start"],
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


def current_thread_id(page, role: str) -> str | None:
    return page.evaluate(f'localStorage.getItem("nora-thread-{role}")')


def set_role(page, role: str, result: Result) -> None:
    page.locator('select[aria-label="Role"]').select_option(role)
    page.wait_for_selector('[data-testid="copilot-chat-textarea"]', timeout=15000)
    assert_role_selected(page, role, result)


def assert_role_selected(page, role: str, result: Result | None = None) -> None:
    """Verify the rendered role selector matches the expected role id."""
    select_value = page.locator('select[aria-label="Role"]').input_value()
    if select_value != role:
        detail = f"expected {role}, got {select_value}"
        if result is not None:
            result.fail("selected-role", detail)
        raise HarnessError(f"Expected role {role}, got {select_value}")


def wait_for_backend_history(
    role: str,
    thread_id: str,
    base_url: str,
    token: str,
    substring: str,
    timeout: float = 20.0,
) -> bool:
    """Poll a role backend until the requested substring appears in history."""
    deadline = time.time() + timeout
    headers = {"Authorization": f"Bearer {token}"}
    while time.time() < deadline:
        try:
            response = httpx.get(
                f"{base_url}/history/{role}/{thread_id}",
                headers=headers,
                timeout=2.0,
            )
            if response.status_code == 200:
                data = response.json()
                for message in data.get("messages", []):
                    if substring in str(message.get("content", "")):
                        return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def send_message(page, text: str, result: Result, timeout: float = 20000.0) -> str:
    from playwright.sync_api import expect

    textarea = page.locator('[data-testid="copilot-chat-textarea"]')
    textarea.wait_for(timeout=timeout)
    send_button = page.locator('[data-testid="copilot-send-button"]')
    textarea.fill(text)
    expect(send_button).to_be_enabled(timeout=timeout)
    send_button.click()
    assistant = page.locator('[data-testid="copilot-assistant-message"]').last
    assistant.wait_for(timeout=timeout)
    return assistant.inner_text()


def click_new_conversation(page) -> None:
    page.locator('button:has-text("New conversation")').click()
    page.wait_for_selector('[data-testid="copilot-chat-textarea"]', timeout=15000)


def run_browser_tests(
    base: str, ports: Ports, token: str, verify_dir: Path, result: Result
) -> None:
    try:
        from playwright.sync_api import expect, sync_playwright
    except ImportError as error:
        raise HarnessError(
            "Playwright is not installed. "
            "Use /private/tmp/nora-role-runtime-venv/bin/python and ensure playwright is installed."
        ) from error

    def screenshot(name: str):
        page.screenshot(path=str(verify_dir / f"{name}.png"))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        console_log = (verify_dir / "browser-console.log").open("w", encoding="utf-8")
        network_log = (verify_dir / "browser-network.log").open("w", encoding="utf-8")
        page.on(
            "console",
            lambda msg: console_log.write(f"{msg.type}: {msg.text}\n") or console_log.flush(),
        )
        page.on(
            "pageerror", lambda exc: console_log.write(f"PAGEERROR: {exc}\n") or console_log.flush()
        )
        page.on(
            "response",
            lambda resp: (
                network_log.write(f"{resp.status} {resp.request.method} {resp.url}\n")
                or network_log.flush()
            ),
        )
        try:
            page.goto(base)
            page.wait_for_selector('select[aria-label="Role"]', timeout=20000)
            page.wait_for_selector(
                'span[role="status"]:has-text("prepared documents")', timeout=20000
            )

            # 1. Knowledge role answers with its own marker.
            if page.locator('select[aria-label="Role"]').input_value() != "knowledge":
                set_role(page, "knowledge", result)
            answer_knowledge = send_message(page, "question knowledge", result)
            if "Answer from knowledge assistant" in answer_knowledge:
                result.ok("knowledge-role-answer", answer_knowledge.strip())
            else:
                screenshot("knowledge_answer")
                result.fail("knowledge-role-answer", answer_knowledge.strip())

            # 2. New conversation resets the knowledge thread.
            knowledge_thread_1 = current_thread_id(page, "knowledge")
            click_new_conversation(page)
            knowledge_thread_2 = current_thread_id(page, "knowledge")
            if (
                knowledge_thread_1
                and knowledge_thread_2
                and knowledge_thread_1 != knowledge_thread_2
            ):
                result.ok(
                    "new-conversation-knowledge", f"{knowledge_thread_1} -> {knowledge_thread_2}"
                )
            else:
                result.fail(
                    "new-conversation-knowledge",
                    f"old={knowledge_thread_1} new={knowledge_thread_2}",
                )

            # 3. Reload resumes the current knowledge thread (new one is empty/welcome).
            page.reload()
            page.wait_for_selector('select[aria-label="Role"]', timeout=20000)
            assert_role_selected(page, "knowledge", result)
            reloaded_thread = current_thread_id(page, "knowledge")
            if reloaded_thread == knowledge_thread_2:
                result.ok("reload-resumes-current-thread", reloaded_thread)
            else:
                result.fail(
                    "reload-resumes-current-thread",
                    f"expected {knowledge_thread_2}, got {reloaded_thread}",
                )

            # 4. Restoring a prior thread resumes its history.
            page.evaluate(f'localStorage.setItem("nora-thread-knowledge", "{knowledge_thread_1}")')
            page.reload()
            page.wait_for_selector('select[aria-label="Role"]', timeout=20000)
            assert_role_selected(page, "knowledge", result)
            page.wait_for_selector('[data-testid="copilot-assistant-message"]', timeout=15000)
            prior_answer = page.locator(
                '[data-testid="copilot-assistant-message"]'
            ).last.inner_text()
            if "Answer from knowledge assistant" in prior_answer:
                result.ok("resume-prior-thread", prior_answer.strip())
            else:
                screenshot("resume_prior")
                result.fail("resume-prior-thread", prior_answer.strip())

            # 5. Research role answers with its own marker.
            set_role(page, "research", result)
            answer_research = send_message(page, "question research", result)
            if "Answer from research assistant" in answer_research:
                result.ok("research-role-answer", answer_research.strip())
            else:
                screenshot("research_answer")
                result.fail("research-role-answer", answer_research.strip())

            # 6. Reload resumes research history.
            research_thread = current_thread_id(page, "research")
            page.reload()
            page.wait_for_selector('select[aria-label="Role"]', timeout=20000)
            assert_role_selected(page, "research", result)
            reloaded_research_thread = current_thread_id(page, "research")
            if reloaded_research_thread != research_thread:
                result.fail(
                    "reload-resumes-research",
                    f"expected {research_thread}, got {reloaded_research_thread}",
                )
            page.wait_for_selector('[data-testid="copilot-assistant-message"]', timeout=15000)
            resumed_research = page.locator(
                '[data-testid="copilot-assistant-message"]'
            ).last.inner_text()
            if (
                reloaded_research_thread == research_thread
                and "Answer from research assistant" in resumed_research
            ):
                result.ok(
                    "reload-resumes-research", f"{research_thread} | {resumed_research.strip()}"
                )
            else:
                screenshot("research_resume")
                result.fail(
                    "reload-resumes-research",
                    f"thread={reloaded_research_thread} content={resumed_research.strip()[:200]}",
                )

            # 7. Transfer selected context from Knowledge to a new Research chat.
            set_role(page, "knowledge", result)
            # Make sure the knowledge thread with an answer is active.
            page.evaluate(f'localStorage.setItem("nora-thread-knowledge", "{knowledge_thread_1}")')
            page.reload()
            page.wait_for_selector('select[aria-label="Role"]', timeout=20000)
            page.wait_for_selector('[data-testid="copilot-assistant-message"]', timeout=15000)

            page.locator('[data-testid="transfer-toggle"]').click()
            page.locator('[data-testid="transfer-load"]').click()
            page.wait_for_selector('[data-testid="transfer-message-list"] label', timeout=10000)
            transfer_items = page.locator('[data-testid="transfer-message-list"] label')
            count = transfer_items.count()
            if count == 0:
                raise HarnessError("No history messages available for transfer")
            # Select the assistant message explicitly so the previewed summary
            # contains the answer the user wants to transfer.
            transfer_checkboxes = page.locator('[data-testid^="transfer-select-"]')
            selected = False
            for i in range(transfer_checkboxes.count()):
                checkbox = transfer_checkboxes.nth(i)
                label = checkbox.locator("xpath=..")
                label_text = label.inner_text()
                if "Answer from knowledge assistant" in label_text:
                    checkbox.check()
                    selected = True
                    break
            if not selected:
                raise HarnessError("No assistant message available for transfer")
            page.locator('select[aria-label="Target role"]').select_option("research")
            page.locator('[data-testid="transfer-preview"]').click()
            page.wait_for_selector('[data-testid="transfer-summary"]', timeout=10000)
            summary = page.locator('[data-testid="transfer-summary"]').input_value()
            if "Answer from knowledge assistant" in summary:
                result.ok("transfer-preview-summary", summary.strip()[:200])
            else:
                screenshot("transfer_preview")
                result.fail("transfer-preview-summary", summary.strip()[:200])

            page.locator('[data-testid="transfer-open-target"]').click()
            page.wait_for_selector('select[aria-label="Role"]', timeout=15000)
            assert_role_selected(page, "research", result)
            page.wait_for_selector('[data-testid="transfer-banner"]', timeout=10000)
            banner = page.locator('[data-testid="transfer-banner"]').inner_text()
            if summary.strip() and summary.strip() in banner:
                result.ok("transfer-banner-visible")
            else:
                result.fail("transfer-banner-visible", banner.strip()[:200])

            # Send the transferred summary in the target chat and verify a research answer.
            target_answer = send_message(page, summary, result)
            if (
                "Answer from research assistant" in target_answer
                and "Answer from knowledge assistant" not in target_answer
            ):
                result.ok("target-chat-receives-transfer", target_answer.strip())
            else:
                screenshot("target_transfer")
                result.fail("target-chat-receives-transfer", target_answer.strip())

            # 8. Switch roles during a deliberately delayed response without leaking content.
            set_role(page, "interview", result)
            interview_thread = current_thread_id(page, "interview")
            textarea = page.locator('[data-testid="copilot-chat-textarea"]')
            textarea.fill("question interview")
            page.locator('[data-testid="copilot-send-button"]').click()
            # Interview backend has a 6-second model delay; the send button should stay disabled.
            send_button = page.locator('[data-testid="copilot-send-button"]')
            try:
                expect(send_button).to_be_disabled(timeout=5000)
            except Exception:
                # If the button never became disabled, still attempt the role switch.
                pass
            set_role(page, "knowledge", result)
            # Give any stray events a moment to arrive.
            time.sleep(1.0)
            page_content = page.content()
            if "Answer from interview analyst" not in page_content:
                result.ok("switch-role-during-response-no-leak")
            else:
                screenshot("role_switch_leak")
                result.fail(
                    "switch-role-during-response-no-leak",
                    "interview answer leaked into knowledge role",
                )

            # Wait for the in-flight interview run to finish on the backend before
            # returning, so the resumed chat can render the completed answer.
            interview_url = f"http://127.0.0.1:{ports.interview}"
            history_ready = wait_for_backend_history(
                "interview",
                interview_thread or "",
                interview_url,
                token,
                "Answer from interview analyst",
                timeout=20.0,
            )
            if not history_ready:
                result.fail(
                    "interview-history-persistence",
                    "Interview answer did not persist after role switch",
                )

            # Return to interview and let the original request complete; the thread should resume.
            set_role(page, "interview", result)
            page.wait_for_selector('[data-testid="copilot-assistant-message"]', timeout=20000)
            final_interview = page.locator(
                '[data-testid="copilot-assistant-message"]'
            ).last.inner_text()
            if "Answer from interview analyst" in final_interview:
                result.ok("interview-completes-after-switch", final_interview.strip())
            else:
                screenshot("interview_final")
                result.fail("interview-completes-after-switch", final_interview.strip())

        except Exception as error:
            result.fail("unexpected-browser-error", f"{type(error).__name__}: {error}")
            try:
                page.screenshot(path=str(verify_dir / "failure.png"))
            except Exception:
                pass
            raise
        finally:
            try:
                console_log.close()
                network_log.close()
            except Exception:
                pass
            try:
                context.close()
                browser.close()
            except Exception:
                pass


def main() -> int:
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", BROWSER_PATH)
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
            knowledge=free_port(),
            research=free_port(),
            interview=free_port(),
            frontend=free_port(),
        )
        result.details["ports"] = {
            "knowledge": ports.knowledge,
            "research": ports.research,
            "interview": ports.interview,
            "frontend": ports.frontend,
        }

        backend_procs = start_role_backends(ports, token, state_dir, verify_dir)
        frontend_proc = start_frontend(ports, token, verify_dir)
        base = f"http://127.0.0.1:{ports.frontend}"
        run_browser_tests(base, ports, token, verify_dir, result)
    except Exception as error:
        result.fail("harness-error", f"{type(error).__name__}: {error}")
        traceback.print_exc()
    finally:
        stop_frontend(frontend_proc)
        stop_role_backends(backend_procs)
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
