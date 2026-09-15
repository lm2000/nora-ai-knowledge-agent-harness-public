#!/usr/bin/env python3
"""Bounded live-provider smoke test for the role-runtime adapters.

Uses harmless synthetic prompts. Requires one configured provider token:
  - NORA_OLLAMA_TOKEN + NORA_OLLAMA_URL for Ollama Cloud
  - NORA_FIREWORKS_TOKEN for Fireworks.ai

The script exits 0 if at least one live provider answers; exits 2 if no
provider is configured; exits 1 on unexpected behavior. No private corpus or
native OpenAI is used.
"""

import asyncio
import os

from nora.config import credential
from nora.providers import ProviderSpec, build_fireworks, build_ollama


def _ollama_spec() -> ProviderSpec | None:
    url = os.environ.get("NORA_OLLAMA_URL", "https://ollama.com")
    model = os.environ.get("NORA_OLLAMA_MODEL", "gpt-oss:20b")
    if not credential("OLLAMA_TOKEN", required=False):
        return None
    return ProviderSpec(
        provider="ollama",
        model=model,
        base_url=url,
        token_name="OLLAMA_TOKEN",
    )


def _fireworks_spec() -> ProviderSpec | None:
    token = credential("FIREWORKS_TOKEN", required=False)
    if not token:
        return None
    model = os.environ.get("NORA_FIREWORKS_MODEL", "accounts/fireworks/models/kimi-k3")
    return ProviderSpec(
        provider="fireworks",
        model=model,
        base_url="https://api.fireworks.ai/inference/v1",
        token_name="FIREWORKS_TOKEN",
    )


async def _test_ollama() -> bool:
    spec = _ollama_spec()
    if spec is None:
        return False
    model = build_ollama(spec, timeout=60)
    result = await model.ainvoke("Say 'smoke test ok' and nothing else.")
    print("Ollama result:", result.content)
    return "smoke test ok" in result.content.lower()


async def _test_fireworks() -> bool:
    spec = _fireworks_spec()
    if spec is None:
        return False
    model = build_fireworks(spec, timeout=60)
    result = await model.ainvoke("Say 'smoke test ok' and nothing else.")
    print("Fireworks result:", result.content)
    return "smoke test ok" in result.content.lower()


async def main() -> int:
    if not _ollama_spec() and not _fireworks_spec():
        print("No live provider token configured; smoke test not run.")
        print("Set NORA_OLLAMA_TOKEN or NORA_FIREWORKS_TOKEN to exercise a live route.")
        return 2

    results = await asyncio.gather(_test_ollama(), _test_fireworks(), return_exceptions=True)
    live_ok = any(r is True for r in results)
    if not live_ok:
        print("No live provider returned the expected response.")
        for r in results:
            if isinstance(r, Exception):
                print("  error:", r)
        return 1

    print("Provider smoke passed: at least one live route answered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
