import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from nora.bootstrap import initialize
from nora.budget import BudgetExceeded, RequestBudget
from nora.config import ConfigurationError, Settings, credential
from nora.evaluation import evaluate, load_queries


def test_secret_files_and_errors_do_not_disclose_value(tmp_path):
    path = tmp_path / "token"
    path.write_text("synthetic-test-token\n")
    assert credential("MCP_TOKEN", env={"NORA_MCP_TOKEN_FILE": str(path)}) == "synthetic-test-token"
    with pytest.raises(ConfigurationError) as error:
        credential(
            "MCP_TOKEN",
            env={"NORA_MCP_TOKEN_FILE": str(path), "NORA_MCP_TOKEN": "synthetic-test-token"},
        )
    assert "synthetic-test-token" not in str(error.value)
    with pytest.raises(ConfigurationError):
        credential("MCP_TOKEN", env={"NORA_MCP_TOKEN": "one\ntwo"})


@pytest.mark.parametrize(
    "env",
    [
        {"NORA_DAILY_LIMIT": "0"},
        {"NORA_CONCURRENCY": "bad"},
        {"NORA_OLLAMA_URL": "https://user:password@example.com"},
        {"NORA_RETRIEVAL_URL": "file:///tmp/mcp"},
        {"NORA_COLLECTION": "../index"},
    ],
)
def test_invalid_settings_fail_early(env):
    with pytest.raises(ConfigurationError):
        Settings.from_env(env)


def test_init_is_idempotent_and_preserves_existing_credentials(tmp_path):
    root = tmp_path / "secrets"
    initialize(root)
    saved = {p.name: p.read_bytes() for p in root.iterdir()}
    initialize(root)
    assert {p.name: p.read_bytes() for p in root.iterdir()} == saved
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in root.iterdir())
    assert root.stat().st_mode & 0o777 == 0o700


def test_daily_budget_is_atomic_across_instances(tmp_path):
    path = tmp_path / "counter.sqlite3"
    budgets = [RequestBudget(path, 7) for _ in range(3)]

    def take(index):
        try:
            return budgets[index % 3].take(day="2026-01-01")
        except BudgetExceeded:
            return None

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(take, range(40)))
    assert sorted(n for n in results if n is not None) == list(range(1, 8))
    assert budgets[0].take(day="2026-01-02") == 1


def test_imports_need_no_credentials_models_or_connections():
    source = "import nora.config, nora.embedding, nora.retrieval, nora.coordination; import sys; assert 'torch' not in sys.modules"
    environment = {key: value for key, value in os.environ.items() if not key.startswith("NORA_")}
    result = subprocess.run(
        [sys.executable, "-c", source], env=environment, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "content", [[], {"queries": []}, [{"id": "x", "query": "Missing labels"}], ["bad"]]
)
def test_invalid_evaluation_fixture_rejected(tmp_path, content):
    path = tmp_path / "queries.json"
    path.write_text(json.dumps(content))
    with pytest.raises(ValueError):
        load_queries(path)


async def test_evaluation_distinguishes_misses_from_invalid_responses():
    queries = load_queries(Path(__file__).resolve().parents[1] / "examples/queries.json")

    class Knowledge:
        payload = {"results": []}

        async def call(self, name, arguments):
            return self.payload

    client = Knowledge()
    result = await evaluate(queries, client, {"hit1": 1, "hit5": 1, "mrr5": 1})
    assert result["count"] == 3 and not result["pass"] and result["hit5"] == 0
    client.payload = {"error": "unavailable"}
    with pytest.raises(ValueError, match="not a scored miss"):
        await evaluate(queries, client, {"hit1": 1, "hit5": 1, "mrr5": 1})
