#!/usr/bin/env python3
"""Serve the production BGE HTTP endpoint with a deterministic encoder double.

This is an acceptance harness, not production code. It proves that the real
`nora.bge_server` stack forwards the HTTP `query` flag to the encoder and
applies bounded admission control when encoding is slow.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

import uvicorn
from doubles import DeterministicEncoderDouble, SlowEncoderDouble

from nora.bge_server import create_app
from nora.config import Settings, credential


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8002
    token = credential("BGE_TOKEN")
    slow = os.environ.get("NORA_BGE_SLOW_SECONDS", "")
    if slow:
        encoder = SlowEncoderDouble(delay_seconds=float(slow))
    else:
        encoder = DeterministicEncoderDouble()
    app = create_app(settings=Settings(), encoder=encoder, token=token)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="error")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
