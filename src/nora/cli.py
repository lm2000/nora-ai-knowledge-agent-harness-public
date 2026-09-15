"""Explicit local administration commands; importing the CLI runs no jobs."""

import argparse
import asyncio
import json
import os
import sys
from contextlib import closing
from pathlib import Path

from nora.config import Settings, credential


def _acceptance_tokenizer():
    """Whitespace tokenizer used only when NORA_ACCEPTANCE_TOKENIZER_DOUBLE is set."""
    import re

    class _WhitespaceTokenizer:
        def __call__(self, text, add_special_tokens=False, return_offsets_mapping=False, **kwargs):
            spans = [m.span() for m in re.finditer(r"\S+", text)]
            input_ids = list(range(len(spans) + (2 if add_special_tokens else 0)))
            result = {"input_ids": input_ids}
            if return_offsets_mapping:
                result["offset_mapping"] = spans
            return result

    return _WhitespaceTokenizer()


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="nora", description="Prepare, serve and evaluate a knowledge assistant"
    )
    commands = root.add_subparsers(dest="command", required=True)
    init = commands.add_parser(
        "init", help="Create missing runtime credentials without overwriting them"
    )
    init.add_argument("--directory", type=Path, default=Path(".runtime/secrets"))
    cache = commands.add_parser("cache-model", help="Download the pinned public BGE model")
    cache.add_argument("--directory", type=Path, default=Path(".runtime/models/bge"))
    conversion = commands.add_parser(
        "convert", help="Extract a document with optional Docling support"
    )
    conversion.add_argument("source", type=Path)
    conversion.add_argument("output", type=Path)
    prepare = commands.add_parser("prepare", help="Prepare and encode documents into a new bundle")
    prepare.add_argument("input", type=Path)
    prepare.add_argument("output", type=Path)
    prepare.add_argument("--model-path")
    for name in ("import", "verify"):
        command = commands.add_parser(name, help=f"{name.title()} a prepared bundle against Qdrant")
        command.add_argument("directory", type=Path)
        command.add_argument("--collection")

    job = commands.add_parser("job", help="Run one manual ingestion job stage")
    job_commands = job.add_subparsers(dest="job", required=True)
    job_convert = job_commands.add_parser("convert", help="Docling conversion job")
    job_convert.add_argument("source", type=Path)
    job_convert.add_argument("output", type=Path)
    job_prepare = job_commands.add_parser("prepare", help="Deterministic preparation job")
    job_prepare.add_argument("extracted", type=Path)
    job_prepare.add_argument("release", type=Path)
    job_embed = job_commands.add_parser("embed", help="Batch embedding job")
    job_embed.add_argument("release", type=Path)
    job_embed.add_argument("--collection")
    job_import = job_commands.add_parser("import", help="Index import/verify job")
    job_import.add_argument("release", type=Path)

    update = commands.add_parser(
        "knowledge-update", help="Run the four ingestion jobs and activate a new release"
    )
    update.add_argument("source", type=Path)
    update.add_argument("releases", type=Path)
    update.add_argument("--collection")

    activate_cmd = commands.add_parser("activate", help="Atomically activate a validated release")
    activate_cmd.add_argument("releases", type=Path)
    activate_cmd.add_argument("release", type=Path)
    activate_cmd.add_argument("--gcs-manifest", type=Path)
    activate_cmd.add_argument("--gcs-pointer")
    activate_cmd.add_argument("--gcs-bucket")
    activate_cmd.add_argument("--gcs-prefix")

    rollback_cmd = commands.add_parser(
        "rollback", help="Activate the previous release from the history log"
    )
    rollback_cmd.add_argument("releases", type=Path)
    rollback_cmd.add_argument("--gcs-pointer")

    serve = commands.add_parser("serve", help="Start one service in this process")
    serve.add_argument("service", choices=["retrieval", "coordination", "bge", "role"])
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int)
    serve.add_argument("--role", default="", help="Role for service=role (defaults to NORA_ROLE)")
    evaluate = commands.add_parser(
        "evaluate", help="Run labeled questions through the configured MCP service"
    )
    evaluate.add_argument("--queries", type=Path, required=True)
    evaluate.add_argument("--hit1", type=float, default=0.5)
    evaluate.add_argument("--hit5", type=float, default=0.5)
    evaluate.add_argument("--mrr5", type=float, default=0.5)
    evaluate.add_argument("--output", type=Path)
    return root


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        settings = Settings.from_env()
        if args.command == "init":
            from nora.bootstrap import initialize

            result = initialize(args.directory)
        elif args.command == "cache-model":
            from nora.embedding import cache_model

            cache_model(args.directory)
            result = {"cached": True}
        elif args.command == "convert":
            from nora.conversion import convert

            result = convert(args.source, args.output)
        elif args.command == "prepare":
            from nora.embedding import BGEEncoder
            from nora.preparation import prepare

            result = prepare(
                args.input, args.output, BGEEncoder(args.model_path or settings.model_path)
            )
        elif args.command in {"import", "verify"}:
            from nora.indexing import connect, import_bundle, verify_bundle

            with closing(connect(settings)) as client:
                function = import_bundle if args.command == "import" else verify_bundle
                result = function(client, args.collection or settings.collection, args.directory)
        elif args.command == "job":
            from nora.bge_client import BGEClient
            from nora.embedding import BGEEncoder
            from nora.jobs import run_convert, run_embed, run_import_verify, run_prepare

            if args.job == "convert":
                result = run_convert(args.source, args.output)
            elif args.job == "prepare":
                if os.environ.get("NORA_ACCEPTANCE_TOKENIZER_DOUBLE"):
                    tokenizer = _acceptance_tokenizer()
                else:
                    from nora.embedding import BGEEncoder

                    encoder = BGEEncoder(settings.model_path)
                    tokenizer = encoder.tokenizer
                result = run_prepare(args.extracted, args.release, tokenizer)
            elif args.job == "embed":
                client = BGEClient.from_settings(settings)
                result = run_embed(args.release, client, qdrant_collection=args.collection)
            elif args.job == "import":
                result = run_import_verify(args.release, settings)
        elif args.command == "knowledge-update":
            from nora.bge_client import BGEClient
            from nora.embedding import BGEEncoder
            from nora.jobs import knowledge_update

            client = BGEClient.from_settings(settings)
            result = knowledge_update(
                args.source, args.releases, settings, client, collection=args.collection
            )
        elif args.command == "activate":
            from nora.jobs import _publisher_gcs_client, activate

            kwargs = {}
            if args.gcs_pointer:
                from nora.documents import parse_gs_url

                bucket, pointer_object = parse_gs_url(args.gcs_pointer)
                kwargs = {
                    "gcs_pointer": (bucket, pointer_object),
                    "gcs_client": _publisher_gcs_client(settings),
                    "bucket": args.gcs_bucket or bucket,
                    "prefix": args.gcs_prefix or "",
                }
            elif args.gcs_manifest:
                kwargs = {
                    "gcs_manifest_path": args.gcs_manifest,
                    "gcs_client": _publisher_gcs_client(settings),
                    "bucket": args.gcs_bucket or "",
                    "prefix": args.gcs_prefix or "",
                }
            result = {"current": str(activate(args.releases, args.release, **kwargs))}
        elif args.command == "rollback":
            from nora.jobs import _publisher_gcs_client, rollback

            kwargs = {}
            pointer = args.gcs_pointer or settings.gcs_pointer
            if pointer:
                from nora.documents import parse_gs_url

                bucket, pointer_object = parse_gs_url(pointer)
                kwargs = {
                    "gcs_pointer": (bucket, pointer_object),
                    "gcs_client": _publisher_gcs_client(settings),
                }
            result = {"current": str(rollback(args.releases, **kwargs))}
        elif args.command == "serve":
            import uvicorn

            if args.service == "bge":
                uvicorn.run(
                    "nora.bge_server:create_app",
                    factory=True,
                    host=args.host,
                    port=args.port or 8002,
                )
            elif args.service == "role":
                role = args.role or settings.role
                if role not in {"knowledge", "research", "interview"}:
                    raise ValueError("Set --role or NORA_ROLE to a valid role")
                # Make the explicit CLI role available to the factory app. Settings is
                # re-read inside create_app, so the runtime role must be in the environment.
                os.environ["NORA_ROLE"] = role
                port = args.port or {"knowledge": 8000, "research": 8003, "interview": 8004}[role]
                uvicorn.run(
                    "nora.coordination:create_app",
                    factory=True,
                    host=args.host,
                    port=port,
                )
            else:
                uvicorn.run(
                    f"nora.{args.service}:create_app",
                    factory=True,
                    host=args.host,
                    port=args.port or (8001 if args.service == "retrieval" else 8000),
                )
            return 0
        else:
            from nora.evaluation import evaluate, load_queries
            from nora.mcp_client import KnowledgeClient

            if args.output and args.output.exists():
                raise FileExistsError("Choose a new evaluation output file")
            knowledge = KnowledgeClient(
                settings.retrieval_url, credential("MCP_TOKEN"), settings.tool_timeout
            )
            result = asyncio.run(
                evaluate(
                    load_queries(args.queries),
                    knowledge,
                    {name: getattr(args, name) for name in ["hit1", "hit5", "mrr5"]},
                )
            )
            if args.output:
                with args.output.open("x", encoding="utf-8") as output:
                    json.dump(result, output, indent=2)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("pass", True) else 1
    except (ValueError, OSError, ImportError) as error:
        # Known local validation errors are useful; HTTP/provider exceptions stay out of output.
        print(
            f"{type(error).__name__}: {error}"
            if isinstance(error, (ValueError, ImportError))
            else f"{type(error).__name__}: could not access the requested local artifact or service",
            file=sys.stderr,
        )
        return 2
    except Exception as error:
        print(
            f"{type(error).__name__}: operation failed; inspect the configured service",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
